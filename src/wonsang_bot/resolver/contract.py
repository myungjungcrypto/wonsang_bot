"""심볼 → 컨트랙트 주소 해결 (선택형, best-effort).

CoinGecko가 설정돼 있으면 심볼로 검색 후 플랫폼별 컨트랙트를 반환한다.
설정이 없거나 실패하면 빈 리스트를 반환(상장 감지/알림은 컨트랙트 없이도 진행).

⚠️ 동일 티커 충돌이 흔하므로, 운영에서는 공지 본문 파싱·체인 힌트·LLM 교차검증으로
   보강해야 한다(현재는 1차 best-effort).
"""
from __future__ import annotations

import logging

from ..config import Config
from ..core.events import Announcement, Contract
from ..httpclient import HttpClient

log = logging.getLogger(__name__)


class ContractResolver:
    def __init__(self, config: Config, http: HttpClient) -> None:
        self.config = config
        self.http = http

    def resolve(self, symbols: list[str], ann: Announcement | None = None) -> list[Contract]:
        if not self.config.coingecko_enabled or not symbols:
            return []
        contracts: list[Contract] = []
        for sym in symbols:
            try:
                contracts.extend(self._resolve_one(sym))
            except Exception:  # noqa: BLE001
                log.exception("컨트랙트 해결 실패 sym=%s", sym)
        return contracts

    def _headers(self) -> dict[str, str]:
        if self.config.coingecko_api_key:
            return {"x-cg-pro-api-key": self.config.coingecko_api_key}
        return {}

    def _resolve_one(self, symbol: str) -> list[Contract]:
        base = self.config.coingecko_base_url.rstrip("/")
        # 1) 심볼/이름으로 검색 → coin id
        search = self.http.get_json(
            f"{base}/search?query={symbol}", headers=self._headers()
        )
        coins = search.get("coins", [])
        match = next(
            (c for c in coins if c.get("symbol", "").upper() == symbol.upper()),
            coins[0] if coins else None,
        )
        if not match:
            return []
        coin_id = match.get("id")
        # 2) 상세에서 플랫폼별 컨트랙트
        detail = self.http.get_json(
            f"{base}/coins/{coin_id}"
            "?localization=false&tickers=false&market_data=false"
            "&community_data=false&developer_data=false",
            headers=self._headers(),
        )
        platforms = detail.get("platforms", {}) or {}
        out: list[Contract] = []
        for chain, addr in platforms.items():
            if chain and addr:
                out.append(Contract(chain=chain, address=addr, via="coingecko"))
        return out
