"""CoinGecko: 컨트랙트 → 같은 코인의 전체 체인 컨트랙트 매핑.

체인마다 컨트랙트가 다른 같은 코인을 식별하는 핵심. 공지의 컨트랙트(예: ETH)를
넣으면 그 코인의 모든 체인 주소(BSC/Solana 등)를 돌려줘 → 진짜 유동성 있는
체인에서 매수가를 잡을 수 있다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..config import Config
from ..httpclient import HttpClient

log = logging.getLogger(__name__)

# CoinGecko 플랫폼 id → 우리 canonical 체인
CG_PLATFORM_TO_CHAIN = {
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
# 우리 체인 → CoinGecko 플랫폼 id (컨트랙트 조회 URL용)
CHAIN_TO_CG_PLATFORM = {v: k for k, v in CG_PLATFORM_TO_CHAIN.items()}
CHAIN_TO_CG_PLATFORM["evm"] = "ethereum"  # 미상 EVM은 이더리움으로 시도


def parse_platforms(payload) -> dict[str, str]:
    """CoinGecko 코인 응답 → {our_chain: address} (전체 체인)."""
    plats = (payload or {}).get("platforms", {}) if isinstance(payload, dict) else {}
    out: dict[str, str] = {}
    for cg_plat, addr in plats.items():
        ch = CG_PLATFORM_TO_CHAIN.get(cg_plat)
        if ch and addr:
            out[ch] = addr
    return out


def parse_symbol(payload) -> str | None:
    """CoinGecko 코인 응답 → 심볼(소문자). 없으면 None."""
    sym = (payload or {}).get("symbol") if isinstance(payload, dict) else None
    return sym.strip().lower() if isinstance(sym, str) and sym.strip() else None


@dataclass(slots=True)
class ResolvedToken:
    symbol: str | None                       # 코인게코가 식별한 심볼(소문자)
    platforms: dict[str, str] = field(default_factory=dict)  # {chain: address} 전체


class CoinGeckoTokens:
    def __init__(self, config: Config, http: HttpClient) -> None:
        self.config = config
        self.http = http
        self.base = config.coingecko_base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        if self.config.coingecko_api_key:
            return {"x-cg-pro-api-key": self.config.coingecko_api_key}
        return {}

    def resolve(self, chain: str, address: str) -> ResolvedToken:
        """(chain, address) → 코인 심볼 + 같은 코인의 전체 체인 주소.

        조회 실패/미식별이면 symbol=None, platforms={원본}. 공지 본문에 여러 토큰
        주소가 섞였을 때(예: USDS 공지에 SKY 주소까지) 심볼로 진짜 상장코인을
        가려내는 데 쓴다.
        """
        plat = CHAIN_TO_CG_PLATFORM.get(chain)
        if not plat:
            return ResolvedToken(None, {chain: address})
        try:
            data = self.http.get_json(
                f"{self.base}/coins/{plat}/contract/{address}", headers=self._headers()
            )
        except Exception:  # noqa: BLE001
            log.debug("CoinGecko 컨트랙트 조회 실패 %s/%s", chain, address, exc_info=True)
            return ResolvedToken(None, {chain: address})
        plats = parse_platforms(data)
        plats.setdefault(chain, address)  # 원본 체인도 포함 보장
        return ResolvedToken(parse_symbol(data), plats)

    def platforms_for(self, chain: str, address: str) -> dict[str, str]:
        """(chain, address) → 같은 코인의 {chain: address} 전체. 실패 시 원본만."""
        return self.resolve(chain, address).platforms
