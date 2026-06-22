"""멀티 거래소 해외가 + 유동성 조회, 그리고 매수처 선택.

매수가 기준(사용자 원칙): **가격이 비슷한 곳 중 유동성(거래대금)이 가장 큰 곳에서 매수**.
미래 따리에서 실제로 할 행동과 동일하게 과거를 백필 → 성공확률이 현실적.

- 각 거래소 kline 에서 (종가, 호가통화 거래대금)을 뽑음. 파서는 순수 함수(테스트).
- 가격 이상치(티커 충돌로 다른 토큰)는 중앙값 밴드 밖이라 제외됨.
- fetch 는 거래소별 격리(개별 실패 무시).

⚠️ 티커 충돌이 '비싼 토큰이 더 유동적'인 경우는 가격밴드로도 못 거를 수 있음
   → 컨트랙트 기반 매칭/DEX 비교가 완전한 해법(로드맵).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from ..config import Config
from ..httpclient import HttpClient
from .returns import _price_at

log = logging.getLogger(__name__)

# (ts_sec, close, quote_volume)
Series3 = list[tuple[float, float, float]]


def _rows3(rows, ts_i: int, close_i: int, qvol_i: int, ms: bool) -> Series3:
    out: Series3 = []
    for r in rows or []:
        try:
            ts = float(r[ts_i]) / (1000.0 if ms else 1.0)
            out.append((ts, float(r[close_i]), float(r[qvol_i])))
        except (ValueError, TypeError, IndexError):
            continue
    return out


# ---------------- 거래소별 순수 파서 (종가 + 호가통화 거래대금) ----------------

def parse_binance(p):  # binance/mexc: [openMs,o,h,l,c,baseVol,closeMs,quoteVol,...]
    return _rows3(p if isinstance(p, list) else [], 0, 4, 7, ms=True)


def parse_bybit(p):    # result.list: [startMs,o,h,l,c,vol,turnover]
    rows = (p or {}).get("result", {}).get("list", []) if isinstance(p, dict) else []
    return _rows3(rows, 0, 4, 6, ms=True)


def parse_okx(p):      # data: [ts,o,h,l,c,vol,volCcy,volCcyQuote,confirm]
    rows = (p or {}).get("data", []) if isinstance(p, dict) else []
    return _rows3(rows, 0, 4, 7, ms=True)


def parse_gate(p):     # [ts, quoteVol, close, high, low, open, baseVol, ...]
    return _rows3(p if isinstance(p, list) else [], 0, 2, 1, ms=False)


def parse_kucoin(p):   # data: [time,open,close,high,low,vol,turnover]
    rows = (p or {}).get("data", []) if isinstance(p, dict) else []
    return _rows3(rows, 0, 2, 6, ms=False)


def parse_bitget(p):   # data: [ts,o,h,l,c,baseVol,quoteVol,...]
    rows = (p or {}).get("data", []) if isinstance(p, dict) else []
    return _rows3(rows, 0, 4, 6, ms=True)


# ---------------- 매수처 선택 (순수) ----------------

def consensus_price(
    venues: dict[str, dict], band: float = 0.12, min_cluster: int = 2
) -> Optional[float]:
    """다수 거래소가 좁은 밴드(±band)로 합의한 가격(군집 대표값). 합의 없으면 None.

    각 가격을 중심으로 ±band 안에 드는 거래소를 세어 가장 큰 군집을 고르고,
    그 군집이 min_cluster 곳 이상이면 **유동성 가중** 대표가를 돌려준다.
    스테이블코인·정상상장은 합의가 생기고(→ 그 가격 신뢰), 시세가 얇거나(<2곳)
    흩어졌으면 None(→ 호출부가 DEX 등 다른 기준을 쓰게).

    용도: 교차체인 DEX가 엉뚱한 풀에서 이상가를 가져와도, CEX 합의가 있으면
    그걸 anchor 로 삼아 정상 CEX 들이 밴드 밖으로 버려지는 사고를 막는다.
    """
    items = [(d["price"], d.get("liq", 0.0) or 0.0) for d in venues.values()
             if d.get("price") and d["price"] > 0]
    if len(items) < min_cluster:
        return None
    best: list[tuple[float, float]] = []
    for center, _ in items:
        cluster = [t for t in items if abs(t[0] - center) / center <= band]
        if (len(cluster) > len(best)
                or (len(cluster) == len(best)
                    and sum(l for _, l in cluster) > sum(l for _, l in best))):
            best = cluster
    if len(best) < min_cluster:
        return None
    liq_sum = sum(l for _, l in best)
    if liq_sum > 0:
        return sum(p * l for p, l in best) / liq_sum          # 유동성 가중 합의가
    return sorted(p for p, _ in best)[len(best) // 2]          # 유동성 0이면 중앙값


def select_buy_venue(
    venues: dict[str, dict], band: float = 0.12, anchor_price: Optional[float] = None
) -> tuple[Optional[float], Optional[str], float]:
    """기준가(±band) 근처 거래소 중 유동성 최대 → (price, venue, price_spread).

    anchor_price 가 주어지면(컨트랙트 검증된 DEX 가격) 그것을 기준 → 티커충돌 제거.
    없으면 중앙값 기준.
    """
    items = [(n, d["price"], d.get("liq", 0.0)) for n, d in venues.items()
             if d.get("price") and d["price"] > 0]
    if not items:
        return None, None, 0.0
    prices = sorted(p for _, p, _ in items)
    ref = anchor_price if (anchor_price and anchor_price > 0) else prices[len(prices) // 2]
    spread = round(prices[-1] / prices[0] - 1.0, 3) if prices[0] > 0 else 0.0
    similar = [t for t in items if ref > 0 and abs(t[1] - ref) / ref <= band]
    pool = similar or items
    name, price, _ = max(pool, key=lambda t: t[2])  # 유동성 최대
    return price, name, spread


# ---------------- 거래소 provider ----------------

class _Exchange:
    name = "base"

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def _url(self, symbol: str, start_ts: float, end_ts: float) -> str:  # pragma: no cover
        raise NotImplementedError

    def _parse(self, payload) -> Series3:  # pragma: no cover
        raise NotImplementedError

    def quote_at(
        self, symbol: str, ts: float, pad_sec: float = 900
    ) -> Optional[tuple[float, float]]:
        """(가격, 유동성=윈도 거래대금합). 실패 시 None."""
        try:
            payload = self.http.get_json(self._url(symbol, ts - 60, ts + pad_sec))
            s = sorted(self._parse(payload))
        except Exception:  # noqa: BLE001 - 거래소별 격리
            log.debug("%s quote_at 실패 %s", self.name, symbol, exc_info=True)
            return None
        if not s:
            return None
        hit = _price_at([(t, c) for t, c, _ in s], ts)
        if hit is None or hit[1] <= 0:
            return None
        liq = sum(qv for _, _, qv in s)
        return hit[1], liq


class Binance(_Exchange):
    name = "binance"

    def _url(self, s, a, b):
        return ("https://data-api.binance.vision/api/v3/klines"
                f"?symbol={s.upper()}USDT&interval=1m"
                f"&startTime={int(a*1000)}&endTime={int(b*1000)}&limit=1000")

    def _parse(self, p):
        return parse_binance(p)


class Mexc(_Exchange):
    name = "mexc"

    def _url(self, s, a, b):
        return ("https://api.mexc.com/api/v3/klines"
                f"?symbol={s.upper()}USDT&interval=1m"
                f"&startTime={int(a*1000)}&endTime={int(b*1000)}&limit=1000")

    def _parse(self, p):
        return parse_binance(p)


class Bybit(_Exchange):
    name = "bybit"

    def _url(self, s, a, b):
        return ("https://api.bybit.com/v5/market/kline?category=spot"
                f"&symbol={s.upper()}USDT&interval=1"
                f"&start={int(a*1000)}&end={int(b*1000)}&limit=1000")

    def _parse(self, p):
        return parse_bybit(p)


class Okx(_Exchange):
    name = "okx"

    def _url(self, s, a, b):
        return ("https://www.okx.com/api/v5/market/history-candles"
                f"?instId={s.upper()}-USDT&bar=1m&after={int(b*1000)}&limit=100")

    def _parse(self, p):
        return parse_okx(p)


class Gate(_Exchange):
    name = "gate"

    def _url(self, s, a, b):
        return ("https://api.gateio.ws/api/v4/spot/candlesticks"
                f"?currency_pair={s.upper()}_USDT&interval=1m"
                f"&from={int(a)}&to={int(b)}")

    def _parse(self, p):
        return parse_gate(p)


class Kucoin(_Exchange):
    name = "kucoin"

    def _url(self, s, a, b):
        return ("https://api.kucoin.com/api/v1/market/candles?type=1min"
                f"&symbol={s.upper()}-USDT&startAt={int(a)}&endAt={int(b)}")

    def _parse(self, p):
        return parse_kucoin(p)


class Bitget(_Exchange):
    name = "bitget"

    def _url(self, s, a, b):
        return ("https://api.bitget.com/api/v2/spot/market/candles"
                f"?symbol={s.upper()}USDT&granularity=1min"
                f"&startTime={int(a*1000)}&endTime={int(b*1000)}&limit=200")

    def _parse(self, p):
        return parse_bitget(p)


_EXCHANGE_CLASSES = [Binance, Bybit, Okx, Mexc, Gate, Kucoin, Bitget]


@dataclass(slots=True)
class Quote:
    buy_price: Optional[float]                 # 매수가(유사가격 중 유동성 최대)
    buy_venue: Optional[str]
    price_spread: float = 0.0                  # 최고/최저 가격차(충돌 진단용)
    venues: dict[str, dict] = field(default_factory=dict)  # name→{price,liq}


class OverseasAggregator:
    def __init__(self, exchanges: list[_Exchange]) -> None:
        self.exchanges = exchanges

    def quote(
        self, symbol: str, ts: float, pad_sec: float = 900,
        extra_venues: Optional[dict[str, dict]] = None,
        anchor_price: Optional[float] = None,
    ) -> Quote:
        """CEX 시세 집계 + extra_venues(예: DEX) 병합 → 매수처 선택.
        anchor_price(컨트랙트 검증 DEX가)가 있으면 그 기준으로 충돌 제거."""
        venues: dict[str, dict] = {}
        for ex in self.exchanges:
            q = ex.quote_at(symbol, ts, pad_sec)
            if q:
                venues[ex.name] = {"price": round(q[0], 8), "liq": round(q[1], 2)}
        if extra_venues:
            venues.update(extra_venues)
        price, venue, spread = select_buy_venue(venues, anchor_price=anchor_price)
        return Quote(buy_price=price, buy_venue=venue, price_spread=spread, venues=venues)


def build_overseas_aggregator(config: Config) -> OverseasAggregator:
    exchanges = [
        cls(HttpClient(timeout=config.http_timeout_sec, proxy=None,
                       user_agent=config.request_user_agent,
                       min_interval=0.15, max_retries=2))
        for cls in _EXCHANGE_CLASSES
    ]
    return OverseasAggregator(exchanges)
