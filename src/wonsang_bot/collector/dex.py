"""DEX 가격/유동성 조회 (Geckoterminal, 무료·무인증).

컨트랙트 주소 기준이라 **티커 충돌이 원천적으로 없음** = '정답 가격' 기준점.
- 토큰의 풀 목록 → 유동성(TVL) 최대 풀 → 그 풀의 분봉 OHLCV → 시점 가격
- parse_* 는 순수 함수(테스트). fetch 는 격리(개별 실패 무시).

⚠️ Geckoterminal 무료 한도(~30req/min) → 호출부 throttle 필요. 엔드포인트/필드는
   라이브 재검증(graceful 라 실패 시 그냥 DEX 미사용).
"""
from __future__ import annotations

import logging
from typing import Optional

from ..httpclient import HttpClient
from .returns import Series, _price_at

log = logging.getLogger(__name__)

GT_BASE = "https://api.geckoterminal.com/api/v2"

# 우리 canonical 체인 → Geckoterminal network id
NET_MAP = {
    "ethereum": "eth", "evm": "eth",
    "bsc": "bsc",
    "solana": "solana",
    "base": "base",
    "arbitrum": "arbitrum",
    "polygon": "polygon_pos",
    "optimism": "optimism",
    "avalanche": "avax",
    "tron": "tron",
    "linea": "linea",
}


def parse_pools(payload) -> list[tuple[str, float]]:
    """토큰 풀 응답 → [(pool_address, reserve_usd)] 유동성 내림차순."""
    data = (payload or {}).get("data", []) if isinstance(payload, dict) else []
    out: list[tuple[str, float]] = []
    for d in data:
        a = (d or {}).get("attributes", {})
        addr = a.get("address")
        try:
            res = float(a.get("reserve_in_usd") or 0)
        except (TypeError, ValueError):
            res = 0.0
        if addr:
            out.append((addr, res))
    out.sort(key=lambda x: -x[1])
    return out


def parse_ohlcv(payload) -> Series:
    """풀 OHLCV 응답 → [(ts_sec, close)]."""
    lst = (
        (payload or {}).get("data", {}).get("attributes", {}).get("ohlcv_list", [])
        if isinstance(payload, dict) else []
    )
    out: Series = []
    for r in lst or []:
        try:
            out.append((float(r[0]), float(r[4])))  # [ts, o, h, l, c, vol]
        except (ValueError, TypeError, IndexError):
            continue
    return out


class GeckoTerminalDEX:
    def __init__(self, http: HttpClient, base: str = GT_BASE) -> None:
        self.http = http
        self.base = base.rstrip("/")

    def quote_at(
        self, chain: str, address: str, ts: float, pad_sec: float = 900
    ) -> Optional[tuple[float, float]]:
        """(가격 USD, 유동성=최대풀 TVL). 실패/없음 시 None."""
        net = NET_MAP.get(chain, chain)
        if not net or not address:
            return None
        try:
            pools = parse_pools(
                self.http.get_json(f"{self.base}/networks/{net}/tokens/{address}/pools")
            )
            if not pools:
                return None
            pool_addr, reserve = pools[0]  # 유동성 최대 풀
            ohlcv = parse_ohlcv(self.http.get_json(
                f"{self.base}/networks/{net}/pools/{pool_addr}/ohlcv/minute"
                f"?aggregate=1&before_timestamp={int(ts + pad_sec)}&limit=100&currency=usd"
            ))
            hit = _price_at(sorted(ohlcv), ts)
            if hit is None or hit[1] <= 0:
                return None
            return hit[1], reserve
        except Exception:  # noqa: BLE001 - graceful
            log.debug("DEX quote 실패 %s/%s", chain, address, exc_info=True)
            return None
