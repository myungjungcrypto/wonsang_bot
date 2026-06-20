"""상장후 실현 수익률 + 상장시점 시총 스냅샷 (CoinGecko, 네트워크 의존).

- coin_id 해소: /search → pick_coin (resolver 재사용, 동명 티커 1차 해소)
- 가격 시계열: /coins/{id}/market_chart/range (글로벌 USD)
- 실현 수익률: returns.peak_return_pct (윈도 내 고점)

망 허용 환경에서만 동작. 여기서는 호출부를 격리하고 순수 계산만 테스트.
"""
from __future__ import annotations

import logging
from typing import Optional

from ..config import Config
from ..httpclient import HttpClient
from ..resolver.contract import pick_coin
from .returns import Series, peak_return_pct

log = logging.getLogger(__name__)


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

    def price_series(
        self, coin_id: str, from_ts: float, to_ts: float, vs: str = "usd"
    ) -> Series:
        url = (
            f"{self.base}/coins/{coin_id}/market_chart/range"
            f"?vs_currency={vs}&from={int(from_ts)}&to={int(to_ts)}"
        )
        data = self.http.get_json(url, headers=self._headers())
        # prices: [[ms, price], ...]
        return [(ms / 1000.0, px) for ms, px in data.get("prices", [])]

    def realized_return(
        self, coin_id: str, listing_ts: float, window_h: float = 48.0, vs: str = "usd"
    ) -> Optional[float]:
        end = listing_ts + window_h * 3600
        series = self.price_series(coin_id, listing_ts - 3600, end, vs)
        return peak_return_pct(series, listing_ts, window_h * 3600)

    def market_cap_at(self, coin_id: str, vs: str = "usd") -> Optional[float]:
        """현재 유통 시총(과거 시점 정확값은 별도 소스 필요 — 근사치)."""
        url = (
            f"{self.base}/coins/{coin_id}"
            "?localization=false&tickers=false&market_data=true"
            "&community_data=false&developer_data=false"
        )
        data = self.http.get_json(url, headers=self._headers())
        md = (data or {}).get("market_data", {})
        cap = (md.get("market_cap") or {}).get(vs)
        return float(cap) if cap else None
