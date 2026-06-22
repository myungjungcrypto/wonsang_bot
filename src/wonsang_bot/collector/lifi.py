"""LI.FI 브릿지 경로 탐색 — 매수 체인 → 업비트 입금 체인 이동 경로.

따리에서 최저가 매수처가 업비트 입금 네트워크와 다른 체인일 때(예: BSC 에서 샀는데
업비트는 Ethereum 입금) **어떤 브릿지로 어떻게 옮기는지**를 찾는다.
LI.FI 공개 API(li.quest, 기본 키 불필요): GET /v1/quote → 사용 브릿지(tool)·예상 수령·
소요시간 반환. 추천 전용(실행은 수동)이라 라우트/도구/시간 파악이 목적.

parse_route 는 순수 함수(테스트). fetch 는 격리(실패 시 None → 브릿지 정보 생략).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from ..config import Config
from ..httpclient import HttpClient

log = logging.getLogger(__name__)

# 우리 canonical 체인 → LI.FI 체인 키
LIFI_CHAIN = {
    "ethereum": "eth", "bsc": "bsc", "arbitrum": "arb", "polygon": "pol",
    "base": "base", "optimism": "opt", "avalanche": "ava", "solana": "sol",
    "linea": "lna", "tron": "tron",
}
# fromAddress 기본값(추천 전용이라 실제 지갑 불필요 — 견적/도구 파악용 placeholder)
_PLACEHOLDER_EVM = "0x0000000000000000000000000000000000000000"


def parse_route(payload: Any) -> dict | None:
    """LI.FI /quote 응답 → {tool, to_amount, duration_sec, from_amount}. 못 읽으면 None."""
    if not isinstance(payload, dict):
        return None
    est = payload.get("estimate") or {}
    tool = payload.get("tool")
    details = payload.get("toolDetails") or {}
    name = details.get("name") or tool
    if not name:
        return None
    out: dict[str, Any] = {"tool": name}
    if est.get("toAmount") is not None:
        out["to_amount"] = str(est.get("toAmount"))
    if est.get("fromAmount") is not None:
        out["from_amount"] = str(est.get("fromAmount"))
    dur = est.get("executionDuration")
    if dur is not None:
        try:
            out["duration_sec"] = int(float(dur))
        except (TypeError, ValueError):
            pass
    return out


class LiFiClient:
    def __init__(self, config: Config, http: HttpClient) -> None:
        self.config = config
        self.http = http
        self.base = config.lifi_base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        key = self.config.lifi_api_key
        return {"x-lifi-api-key": key} if key else {}

    def route(
        self, from_chain: str, from_token: str, to_chain: str, to_token: str,
        from_amount: str, from_address: Optional[str] = None,
    ) -> dict | None:
        """매수체인 토큰 → 입금체인 토큰 브릿지 경로 1건. 실패/없음 시 None."""
        fc, tc = LIFI_CHAIN.get(from_chain), LIFI_CHAIN.get(to_chain)
        if not fc or not tc or not from_token or not to_token:
            return None
        params = (
            f"fromChain={fc}&toChain={tc}&fromToken={from_token}&toToken={to_token}"
            f"&fromAmount={from_amount}&fromAddress={from_address or _PLACEHOLDER_EVM}"
        )
        try:
            data = self.http.get_json(f"{self.base}/quote?{params}", headers=self._headers())
        except Exception:  # noqa: BLE001 - 경로 없음/한도 등은 graceful
            log.debug("LI.FI 경로 조회 실패 %s→%s", from_chain, to_chain, exc_info=True)
            return None
        route = parse_route(data)
        if route is not None:
            route["from_chain"] = from_chain
            route["to_chain"] = to_chain
        return route
