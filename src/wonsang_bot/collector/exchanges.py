"""멀티 거래소 해외가 조회 + 가용성 집계.

따리 매수 후보 거래소(바이낸스/바이빗/OKX/MEXC/게이트/쿠코인/비트겟)의 특정 시점
USDT 가격을 모두 조회 → 최저가(=매수 유리처) + 어느 거래소에 있었나(가용성 피처).

- kline 파서는 거래소별 순수 함수(테스트). fetch 는 거래소별로 격리하고
  **개별 실패는 무시**(graceful) → 일부 어댑터가 틀려도 나머지로 데이터 수집.
- 어느 거래소에도 없으면(best=None) → 사전 물량 확보 불가(TGE 동시상장/ DEX 전용 의심).

⚠️ 엔드포인트/심볼포맷/응답형식은 라이브에서 거래소별 재검증 필요.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from ..config import Config
from ..httpclient import HttpClient
from .binance import parse_klines as _parse_binance  # [openTime_ms,o,h,l,c,...]
from .returns import Series, _price_at

log = logging.getLogger(__name__)


# ---------------- 거래소별 순수 파서 ----------------

def parse_bybit(payload) -> Series:
    rows = (payload or {}).get("result", {}).get("list", []) if isinstance(payload, dict) else []
    return _idx(rows, 0, 4, ms=True)


def parse_okx(payload) -> Series:
    rows = (payload or {}).get("data", []) if isinstance(payload, dict) else []
    return _idx(rows, 0, 4, ms=True)


def parse_bitget(payload) -> Series:
    rows = (payload or {}).get("data", []) if isinstance(payload, dict) else []
    return _idx(rows, 0, 4, ms=True)


def parse_gate(payload) -> Series:
    # [ts_sec, quote_vol, close, high, low, open, ...]
    rows = payload if isinstance(payload, list) else []
    return _idx(rows, 0, 2, ms=False)


def parse_kucoin(payload) -> Series:
    # data: [[time_sec, open, close, high, low, volume, turnover], ...]
    rows = (payload or {}).get("data", []) if isinstance(payload, dict) else []
    return _idx(rows, 0, 2, ms=False)


def _idx(rows, ts_i: int, close_i: int, ms: bool) -> Series:
    out: Series = []
    for r in rows or []:
        try:
            ts = float(r[ts_i]) / (1000.0 if ms else 1.0)
            out.append((ts, float(r[close_i])))
        except (ValueError, TypeError, IndexError):
            continue
    return out


# ---------------- 거래소 provider ----------------

class _Exchange:
    name = "base"

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def _url(self, symbol: str, start_ts: float, end_ts: float) -> str:  # pragma: no cover
        raise NotImplementedError

    def _parse(self, payload) -> Series:  # pragma: no cover
        raise NotImplementedError

    def price_at(self, symbol: str, ts: float, pad_sec: float = 900) -> Optional[float]:
        try:
            payload = self.http.get_json(self._url(symbol, ts - 60, ts + pad_sec))
            hit = _price_at(sorted(self._parse(payload)), ts)
            return hit[1] if hit else None
        except Exception:  # noqa: BLE001 - 거래소별 실패 격리
            log.debug("%s price_at 실패 %s", self.name, symbol, exc_info=True)
            return None


class Binance(_Exchange):
    name = "binance"

    def _url(self, s, a, b):
        return ("https://data-api.binance.vision/api/v3/klines"
                f"?symbol={s.upper()}USDT&interval=1m"
                f"&startTime={int(a*1000)}&endTime={int(b*1000)}&limit=1000")

    def _parse(self, p):
        return _parse_binance(p if isinstance(p, list) else [])


class Mexc(_Exchange):
    name = "mexc"

    def _url(self, s, a, b):
        return ("https://api.mexc.com/api/v3/klines"
                f"?symbol={s.upper()}USDT&interval=1m"
                f"&startTime={int(a*1000)}&endTime={int(b*1000)}&limit=1000")

    def _parse(self, p):
        return _parse_binance(p if isinstance(p, list) else [])


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
    best_usd: Optional[float]                 # 최저 매수가(=유리처)
    venues: dict[str, float] = field(default_factory=dict)  # 거래소→가격


class OverseasAggregator:
    def __init__(self, exchanges: list[_Exchange]) -> None:
        self.exchanges = exchanges

    def quote(self, symbol: str, ts: float, pad_sec: float = 900) -> Quote:
        venues: dict[str, float] = {}
        for ex in self.exchanges:
            px = ex.price_at(symbol, ts, pad_sec)
            if px and px > 0:
                venues[ex.name] = px
        best = min(venues.values()) if venues else None
        return Quote(best_usd=best, venues=venues)


def build_overseas_aggregator(config: Config) -> OverseasAggregator:
    """거래소별 독립 client(레이트리밋 throttle)로 집계기 구성."""
    exchanges = [
        cls(HttpClient(timeout=config.http_timeout_sec, proxy=None,
                       user_agent=config.request_user_agent,
                       min_interval=0.15, max_retries=2))
        for cls in _EXCHANGE_CLASSES
    ]
    return OverseasAggregator(exchanges)
