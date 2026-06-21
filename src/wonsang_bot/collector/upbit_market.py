"""업비트 마켓목록 + 첫 캔들 기반 백필 (Cloudflare 우회).

공지 API(api-manager.upbit.com)는 Cloudflare 차단이라, 차단 안 되는 공개 API
(api.upbit.com)만으로 과거 케이스를 만든다:
1) /v1/market/all → 현재 KRW 상장 코인
2) 각 코인의 가장 오래된 일봉 → 상장 '날짜' 특정
3) 상장일 분봉 → 첫 체결(상장 시점) + (+5분 매수 / +15분 매도) 수익률

parse_*/realized_return_from_series 는 순수 함수(테스트). fetch 부는 격리.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote

from ..httpclient import HttpClient
from .price import upbit_candles_to_series
from .returns import Series, _price_at, point_return_pct

log = logging.getLogger(__name__)

UPBIT_API = "https://api.upbit.com/v1"


def parse_krw_markets(payload: list) -> list[dict]:
    """market/all 응답 → KRW 마켓만 [{symbol, market, name}]."""
    out: list[dict] = []
    for it in payload or []:
        market = str(it.get("market", ""))
        if not market.startswith("KRW-"):
            continue
        out.append(
            {
                "symbol": market.split("-", 1)[1],
                "market": market,
                "name": " ".join(
                    x for x in [it.get("korean_name"), it.get("english_name")] if x
                ),
            }
        )
    return out


def realized_return_from_series(
    series: Series, entry_offset_sec: float, exit_offset_sec: float
) -> tuple[Optional[float], Optional[float]]:
    """반환: (listing_ts, return_pct). 첫 체결을 상장 시점으로 본다."""
    if not series:
        return None, None
    s = sorted(series)
    listing_ts = s[0][0]
    return listing_ts, point_return_pct(s, listing_ts, entry_offset_sec, exit_offset_sec)


def _fmt(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class UpbitMarketBackfiller:
    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def fetch_krw_markets(self) -> list[dict]:
        payload = self.http.get_json(f"{UPBIT_API}/market/all?isDetails=false")
        return parse_krw_markets(payload if isinstance(payload, list) else [])

    def find_listing_day(self, market: str, max_pages: int = 40) -> Optional[float]:
        """가장 오래된 일봉 시각(상장 날짜, UTC epoch). 없으면 None."""
        to: Optional[str] = None
        oldest: Optional[str] = None
        for _ in range(max_pages):
            url = f"{UPBIT_API}/candles/days?market={market}&count=200"
            if to:
                url += f"&to={quote(to)}"
            rows = self.http.get_json(url)
            if not isinstance(rows, list) or not rows:
                break
            oldest = rows[-1].get("candle_date_time_utc")
            if len(rows) < 200:
                break
            to = oldest
        if not oldest:
            return None
        return datetime.fromisoformat(oldest).replace(tzinfo=timezone.utc).timestamp()

    def fetch_listing_day_minutes(
        self, market: str, listing_day_ts: float, max_pages: int = 10,
        price_key: str = "trade_price",
    ) -> Series:
        """상장일 분봉을 모은다(첫 체결 ~ 그날 분봉)."""
        day_start = (
            datetime.fromtimestamp(listing_day_ts, tz=timezone.utc)
            .replace(hour=0, minute=0, second=0)
            .timestamp()
        )
        series: Series = []
        to = day_start + 24 * 3600
        for _ in range(max_pages):
            url = (
                f"{UPBIT_API}/candles/minutes/1?market={market}"
                f"&count=200&to={quote(_fmt(to))}"
            )
            rows = self.http.get_json(url)
            chunk = upbit_candles_to_series(
                rows if isinstance(rows, list) else [], price_key=price_key
            )
            if not chunk:
                break
            series.extend(chunk)
            oldest_ts = min(t for t, _ in chunk)
            if oldest_ts <= day_start or len(rows) < 200:
                break
            to = oldest_ts
        return sorted(series)

    def listing_and_return(
        self, market: str, entry_offset_sec: float, exit_offset_sec: float
    ) -> tuple[Optional[float], Optional[float]]:
        day = self.find_listing_day(market)
        if day is None:
            return None, None
        series = self.fetch_listing_day_minutes(market, day)
        return realized_return_from_series(series, entry_offset_sec, exit_offset_sec)

    def first_candle(self, market: str) -> tuple[Optional[float], Optional[float]]:
        """KRW-{심볼} 첫 체결 (상장 오픈) → (listing_ts, price).

        첫 1분봉 *종가*(trade_price) 사용 — 시가는 단일가/동시호가 artifact(이상값)가
        섞일 수 있어 종가가 더 안정적·현실적("상장 직후 1분 내 매도").
        """
        day = self.find_listing_day(market)
        if day is None:
            return None, None
        series = self.fetch_listing_day_minutes(market, day, price_key="trade_price")
        if not series:
            return None, None
        ts, px = sorted(series)[0]
        return ts, px

    def price_at(
        self, market: str, ts: float, pad_sec: float = 900
    ) -> Optional[float]:
        """특정 시점(이상 첫 포인트) KRW 가격. KRW-USDT 환율 조회 등에 사용."""
        url = (
            f"{UPBIT_API}/candles/minutes/1?market={market}"
            f"&count=200&to={quote(_fmt(ts + pad_sec))}"
        )
        rows = self.http.get_json(url)
        series = upbit_candles_to_series(rows if isinstance(rows, list) else [])
        hit = _price_at(sorted(series), ts)
        return hit[1] if hit else None
