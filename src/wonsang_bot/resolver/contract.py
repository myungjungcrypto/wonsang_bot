"""심볼 → 컨트랙트 주소 해결.

전략(기능 1의 "컨트랙트로 상장 코인 특정"):
1. 공지 본문 텍스트에서 주소 추출(가장 신뢰도 높음) — 네트워크 불필요
2. CoinGecko로 심볼 검색 → 동명 티커는 시총순위로 1차 해소 → 플랫폼별 컨트랙트
3. 둘을 병합. 본문 주소 == 코인게코 주소면 교차검증(via="body+coingecko")로 승격

CoinGecko가 꺼져 있으면 본문 추출만으로도 동작. 둘 다 실패하면 빈 리스트
(상장 감지/알림 자체는 컨트랙트 없이도 진행).
"""
from __future__ import annotations

import logging

from ..config import Config
from ..core.events import Announcement, Contract
from ..detector.contract_extract import extract_contracts_from_text
from ..httpclient import HttpClient

log = logging.getLogger(__name__)

# CoinGecko 플랫폼 키 → canonical 체인
_CG_PLATFORM_MAP = {
    "ethereum": "ethereum",
    "binance-smart-chain": "bsc",
    "polygon-pos": "polygon",
    "arbitrum-one": "arbitrum",
    "base": "base",
    "optimistic-ethereum": "optimism",
    "avalanche": "avalanche",
    "solana": "solana",
    "tron": "tron",
    "linea": "linea",
}


def norm_cg_platform(key: str) -> str:
    return _CG_PLATFORM_MAP.get(key, key)


def platforms_to_contracts(platforms: dict, via: str = "coingecko") -> list[Contract]:
    out: list[Contract] = []
    for chain, addr in (platforms or {}).items():
        if chain and addr:
            out.append(Contract(chain=norm_cg_platform(chain), address=addr, via=via))
    return out


def pick_coin(coins: list[dict], symbol: str) -> dict | None:
    """동명 티커 1차 해소: 심볼 정확 일치 우선 → 시총순위 높은 것."""
    if not coins:
        return None
    exact = [c for c in coins if str(c.get("symbol", "")).upper() == symbol.upper()]
    pool = exact or coins

    def rank(c: dict) -> int:
        r = c.get("market_cap_rank")
        return r if isinstance(r, int) else 10**9

    return sorted(pool, key=rank)[0]


def merge_contracts(*lists: list[Contract]) -> list[Contract]:
    """주소(대소문자 무시) 기준 병합 + 교차검증.

    - 같은 주소가 body·coingecko 양쪽에 있으면 via='body+coingecko'
    - 체인은 구체적인 값(evm/unknown 제외) 우선
    """
    order: list[str] = []
    info: dict[str, dict] = {}
    for lst in lists:
        for c in lst:
            k = c.address.lower()
            if k not in info:
                info[k] = {"addr": c.address, "chains": [], "vias": set(), "any": c.chain}
                order.append(k)
            if c.chain and c.chain not in ("evm", "unknown") and c.chain not in info[k]["chains"]:
                info[k]["chains"].append(c.chain)
            info[k]["vias"].add(c.via)

    result: list[Contract] = []
    for k in order:
        d = info[k]
        chain = d["chains"][0] if d["chains"] else d["any"]
        vias = d["vias"]
        if {"announcement_body", "coingecko"} <= vias:
            via = "body+coingecko"
        else:
            via = sorted(vias)[0] if vias else "unknown"
        result.append(Contract(chain=chain, address=d["addr"], via=via))
    return result


class ContractResolver:
    def __init__(self, config: Config, http: HttpClient) -> None:
        self.config = config
        self.http = http

    def resolve(
        self,
        symbols: list[str],
        ann: Announcement | None = None,
        body_text: str | None = None,
    ) -> list[Contract]:
        body_contracts = extract_contracts_from_text(body_text)

        cg_contracts: list[Contract] = []
        if self.config.coingecko_enabled and symbols:
            for sym in symbols:
                try:
                    cg_contracts.extend(self._resolve_one(sym))
                except Exception:  # noqa: BLE001
                    log.exception("CoinGecko 해결 실패 sym=%s", sym)

        return merge_contracts(body_contracts, cg_contracts)

    def _headers(self) -> dict[str, str]:
        if self.config.coingecko_api_key:
            return {"x-cg-pro-api-key": self.config.coingecko_api_key}
        return {}

    def _resolve_one(self, symbol: str) -> list[Contract]:
        base = self.config.coingecko_base_url.rstrip("/")
        search = self.http.get_json(f"{base}/search?query={symbol}", headers=self._headers())
        coin = pick_coin(search.get("coins", []), symbol)
        if not coin:
            return []
        detail = self.http.get_json(
            f"{base}/coins/{coin.get('id')}"
            "?localization=false&tickers=false&market_data=false"
            "&community_data=false&developer_data=false",
            headers=self._headers(),
        )
        return platforms_to_contracts(detail.get("platforms", {}))
