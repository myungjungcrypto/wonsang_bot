"""바이낸스 1분봉으로 해외 USDT 가격 조회 (글로벌, 과거 수년치).

따리 백필의 '해외 매수가(공지+5분)' 소스. parse_klines 는 순수 함수(테스트).
공개 마켓데이터 엔드포인트(data-api.binance.vision)는 인증·지역제한 없음.
"""
from __future__ import annotations

import logging
from typing import Optional

from ..httpclient import HttpClient
from .returns import Series, _price_at

log = logging.getLogger(__name__)

BINANCE_BASE = "https://data-api.binance.vision"


def parse_klines(rows: list) -> Series:
    """klines 응답 → [(epoch_sec, close)]. 각 행: [openTime_ms, o, h, l, c, v, ...]."""
    out: Series = []
    for r in rows or []:
        try:
            out.append((float(r[0]) / 1000.0, float(r[4])))
        except (ValueError, TypeError, IndexError):
            continue
    return out


class BinancePriceProvider:
    def __init__(self, http: HttpClient, base: str = BINANCE_BASE) -> None:
        self.http = http
        self.base = base.rstrip("/")

    def klines(
        self, symbol: str, start_ts: float, end_ts: float, interval: str = "1m"
    ) -> Series:
        url = (
            f"{self.base}/api/v3/klines?symbol={symbol.upper()}USDT"
            f"&interval={interval}&startTime={int(start_ts*1000)}"
            f"&endTime={int(end_ts*1000)}&limit=1000"
        )
        rows = self.http.get_json(url)
        return parse_klines(rows if isinstance(rows, list) else [])

    def price_at(self, symbol: str, ts: float, pad_sec: float = 900) -> Optional[float]:
        """ts 시점(이상 첫 포인트) USDT 가격. 데이터 없으면 None."""
        series = self.klines(symbol, ts - 60, ts + pad_sec)
        hit = _price_at(sorted(series), ts)
        return hit[1] if hit else None
