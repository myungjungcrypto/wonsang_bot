"""가격/시총 provider (네트워크 의존).

라벨 방법론: 진입(+5분) → 국내(업비트/빗썸) KRW 캔들 고점 매도.
- 국내 수익률: UpbitKrwPriceProvider / BithumbKrwPriceProvider (KRW 분봉)
- 시총 스냅샷(피처용): CoinGeckoPriceProvider (글로벌 USD)

캔들 파서(_*_to_series)는 순수 함수(테스트). fetch 부는 격리(라이브 재검증).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

from ..config import Config
from ..httpclient import HttpClient
from ..resolver.contract import pick_coin
from .returns import Series, point_return_pct

log = logging.getLogger(__name__)

# 진입 +5분, 매도 +15분(상장 직후 시점 매도, 고점 아님) — collect_cases 에서 override
DEFAULT_ENTRY_OFFSET_SEC = 300.0
DEFAULT_EXIT_OFFSET_SEC = 900.0


# ---------------- 국내 캔들 파서 (순수) ----------------

def upbit_candles_to_series(rows: list[dict]) -> Series:
    """업비트 분봉 응답 → [(epoch_sec, trade_price)]."""
    out: Series = []
    for r in rows or []:
        dt = r.get("candle_date_time_utc")
        px = r.get("trade_price")
        if not dt or px is None:
            continue
        try:
            ts = datetime.fromisoformat(dt).replace(tzinfo=timezone.utc).timestamp()
            out.append((ts, float(px)))
        except (ValueError, TypeError):
            continue
    return out


def bithumb_candles_to_series(rows: list) -> Series:
    """빗썸 candlestick data → [(epoch_sec, close)]. 각 행: [ms, open, close, high, low, vol]."""
    out: Series = []
    for r in rows or []:
        try:
            ts = float(r[0]) / 1000.0
            close = float(r[2])
            out.append((ts, close))
        except (ValueError, TypeError, IndexError):
            continue
    return out


# ---------------- 국내 수익률 provider (네트워크) ----------------

class DomesticPriceProvider:
    def realized_return(
        self, symbol: str, ref_ts: float,
        entry_offset_sec: float = DEFAULT_ENTRY_OFFSET_SEC,
        exit_offset_sec: float = DEFAULT_EXIT_OFFSET_SEC,
    ) -> Optional[float]:  # pragma: no cover - network
        raise NotImplementedError


class UpbitKrwPriceProvider(DomesticPriceProvider):
    """업비트 KRW 분봉(`to` 지원 → 과거 임의 시점 백필 가능)."""

    def __init__(self, http: HttpClient, unit: int = 1, max_pages: int = 12) -> None:
        self.http = http
        self.unit = unit
        self.max_pages = max_pages

    def price_series(self, symbol: str, from_ts: float, to_ts: float) -> Series:
        market = f"KRW-{symbol.upper()}"
        series: Series = []
        cur = to_ts
        for _ in range(self.max_pages):
            to_str = datetime.fromtimestamp(cur, tz=timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            url = (
                f"https://api.upbit.com/v1/candles/minutes/{self.unit}"
                f"?market={market}&count=200&to={quote(to_str)}"
            )
            rows = self.http.get_json(url)
            chunk = upbit_candles_to_series(rows if isinstance(rows, list) else [])
            if not chunk:
                break
            series.extend(chunk)
            earliest = min(t for t, _ in chunk)
            if earliest <= from_ts:
                break
            cur = earliest - 1
        return sorted(series)

    def realized_return(
        self, symbol: str, ref_ts: float,
        entry_offset_sec: float = DEFAULT_ENTRY_OFFSET_SEC,
        exit_offset_sec: float = DEFAULT_EXIT_OFFSET_SEC,
    ) -> Optional[float]:
        series = self.price_series(symbol, ref_ts - 60, ref_ts + exit_offset_sec + 60)
        return point_return_pct(series, ref_ts, entry_offset_sec, exit_offset_sec)


class BithumbKrwPriceProvider(DomesticPriceProvider):
    """빗썸 KRW candlestick. ⚠️ 공개 API는 최근 구간만 → 오래된 상장은 깊이 부족할 수 있음."""

    def __init__(self, http: HttpClient, interval: str = "1m") -> None:
        self.http = http
        self.interval = interval

    def price_series(self, symbol: str, from_ts: float, to_ts: float) -> Series:
        url = f"https://api.bithumb.com/public/candlestick/{symbol.upper()}_KRW/{self.interval}"
        data = self.http.get_json(url)
        rows = data.get("data", []) if isinstance(data, dict) else []
        series = bithumb_candles_to_series(rows)
        return sorted([(t, p) for t, p in series if from_ts <= t <= to_ts])

    def realized_return(
        self, symbol: str, ref_ts: float,
        entry_offset_sec: float = DEFAULT_ENTRY_OFFSET_SEC,
        exit_offset_sec: float = DEFAULT_EXIT_OFFSET_SEC,
    ) -> Optional[float]:
        series = self.price_series(symbol, ref_ts - 60, ref_ts + exit_offset_sec + 60)
        return point_return_pct(series, ref_ts, entry_offset_sec, exit_offset_sec)


def domestic_provider_for(
    source: str, http: HttpClient
) -> Optional[DomesticPriceProvider]:
    if source == "upbit":
        return UpbitKrwPriceProvider(http)
    if source == "bithumb":
        return BithumbKrwPriceProvider(http)
    return None


# ---------------- 시총 스냅샷 (글로벌, 피처용) ----------------

class CoinGeckoPriceProvider:
    def __init__(self, config: Config, http: HttpClient) -> None:
        self.config = config
        self.http = http
        self.base = config.coingecko_base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        if self.config.coingecko_api_key:
            return {"x-cg-pro-api-key": self.config.coingecko_api_key}
        return {}

    def resolve_coin_id(self, symbol: str) -> Optional[str]:
        search = self.http.get_json(
            f"{self.base}/search?query={symbol}", headers=self._headers()
        )
        coin = pick_coin(search.get("coins", []), symbol)
        return coin.get("id") if coin else None

    def market_cap_usd(self, coin_id: str) -> Optional[float]:
        """현재 유통 시총(과거 시점 정확값은 별도 소스 필요 — 근사치)."""
        url = (
            f"{self.base}/coins/{coin_id}"
            "?localization=false&tickers=false&market_data=true"
            "&community_data=false&developer_data=false"
        )
        data = self.http.get_json(url, headers=self._headers())
        md = (data or {}).get("market_data", {})
        cap = (md.get("market_cap") or {}).get("usd")
        return float(cap) if cap else None
