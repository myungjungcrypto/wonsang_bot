"""멀티 거래소 해외가 + 유동성 조회, 그리고 매수처 선택.

매수가 기준(사용자 원칙): **같은 토큰인지 신원으로 확정 → 유동성 적은 곳 제거 →
남은 구매처 중 최저가에서 매수.** 같은 토큰이면 싼 곳이 곧 대박이라 가격으로
거르지 않는다(노이즈는 신원+유동성으로만 거른다).

- 각 거래소 kline 에서 (종가, 호가통화 거래대금)을 뽑음. 파서는 순수 함수(테스트).
- 신원: CEX 는 코인게코 티커(코인 id 의 마켓), DEX 는 컨트랙트 주소로 확정 → 호출부에서.
- fetch 는 거래소별 격리(개별 실패 무시).
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

def choose_buy_venue(
    venues: dict[str, dict], dex_min_liq: float = 30000.0, cex_min_liq: float = 0.0
) -> tuple[Optional[float], Optional[str], float]:
    """유동성 컷을 통과한 구매처 중 **최저가** → (price, venue, price_spread).

    노이즈는 **가격이 아니라 신원+유동성**으로 거른다(신원은 호출 전에 확정):
    - DEX(컨트랙트로 같은 토큰 확정): 풀 reserve >= dex_min_liq 인 것만.
    - CEX(코인게코 티커로 신원 확정): 거래대금 >= cex_min_liq 인 것만.
    같은 토큰이면 더 싼 곳이 곧 더 좋은 매수처(대박) → 살아남은 것 중 최저가 채택.
    venue dict 는 {"price","liq","kind": "cex"|"dex"} 형식.
    """
    kept: list[tuple[str, float, float]] = []
    for name, d in venues.items():
        price = d.get("price")
        if not price or price <= 0:
            continue
        liq = d.get("liq", 0.0) or 0.0
        floor = dex_min_liq if d.get("kind") == "dex" else cex_min_liq
        if liq < floor:
            continue
        kept.append((name, price, liq))
    if not kept:
        return None, None, 0.0
    prices = sorted(p for _, p, _ in kept)
    spread = round(prices[-1] / prices[0] - 1.0, 3) if prices[0] > 0 else 0.0
    name, price, _ = min(kept, key=lambda t: t[1])  # 최저가(같은 토큰이면 싼 게 이득)
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

    def fetch_venues(
        self, symbol: str, ts: float, pad_sec: float = 900,
        only: Optional[set[str]] = None,
    ) -> dict[str, dict]:
        """CEX 시세 집계 → {name: {price, liq, kind:'cex'}}.

        only 가 주어지면(코인게코 티커로 검증된 거래소 집합) 그 거래소만 조회 →
        같은 티커 다른 토큰(충돌) 배제 + 불필요한 호출 절감. None 이면 전체 조회.
        """
        venues: dict[str, dict] = {}
        for ex in self.exchanges:
            if only is not None and ex.name not in only:
                continue
            q = ex.quote_at(symbol, ts, pad_sec)
            if q:
                venues[ex.name] = {"price": round(q[0], 8), "liq": round(q[1], 2),
                                   "kind": "cex"}
        return venues

    def quote(
        self, symbol: str, ts: float, pad_sec: float = 900,
        only: Optional[set[str]] = None,
        extra_venues: Optional[dict[str, dict]] = None,
        dex_min_liq: float = 30000.0, cex_min_liq: float = 0.0,
    ) -> Quote:
        """CEX 집계 + extra_venues(예: DEX) 병합 → 유동성 컷 통과분 중 최저가."""
        venues = self.fetch_venues(symbol, ts, pad_sec, only)
        if extra_venues:
            venues.update(extra_venues)
        price, venue, spread = choose_buy_venue(venues, dex_min_liq, cex_min_liq)
        return Quote(buy_price=price, buy_venue=venue, price_spread=spread, venues=venues)


def build_overseas_aggregator(config: Config) -> OverseasAggregator:
    exchanges = [
        cls(HttpClient(timeout=config.http_timeout_sec, proxy=None,
                       user_agent=config.request_user_agent,
                       min_interval=0.15, max_retries=2))
        for cls in _EXCHANGE_CLASSES
    ]
    return OverseasAggregator(exchanges)
