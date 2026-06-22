"""LunarCrush 소셜 지표 — 라이브 등급예측의 social 피처용.

LunarCrush API v4 (Bearer 키 필요):
  GET {base}/public/coins/{symbol}/v1  → data: galaxy_score, interactions_24h,
      social_dominance, sentiment, alt_rank ...
키 없으면(또는 실패) provider 가 None 반환 → social 피처 우아하게 비활성.

parse_social 은 순수 함수(테스트). fetch 는 격리.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from ..config import Config
from ..httpclient import HttpClient

log = logging.getLogger(__name__)


def parse_social(payload: Any) -> dict | None:
    """LunarCrush 코인 응답 → {galaxy_score, interactions_24h, mentions_per_hour}.

    data 가 dict 또는 [dict] 형태일 수 있음. 못 읽으면 None.
    mentions_per_hour 는 interactions_24h/24 로 환산(velocity 근사).
    """
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if isinstance(data, list):
        data = data[0] if data else None
    if not isinstance(data, dict):
        return None

    def _num(key: str) -> Optional[float]:
        v = data.get(key)
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    galaxy = _num("galaxy_score")
    interactions = _num("interactions_24h")
    out: dict[str, float] = {}
    if galaxy is not None:
        out["galaxy_score"] = galaxy
    if interactions is not None:
        out["interactions_24h"] = interactions
        out["mentions_per_hour"] = interactions / 24.0
    return out or None


class LunarCrushClient:
    def __init__(self, config: Config, http: HttpClient) -> None:
        self.config = config
        self.http = http
        self.base = config.lunarcrush_base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        key = self.config.lunarcrush_api_key
        return {"Authorization": f"Bearer {key}"} if key else {}

    def social_for(self, symbol: str) -> dict | None:
        if not symbol or not self.config.lunarcrush_api_key:
            return None
        url = f"{self.base}/public/coins/{symbol.upper()}/v1"
        try:
            data = self.http.get_json(url, headers=self._headers())
        except Exception:  # noqa: BLE001 - 키 한도/없는 심볼 등은 그냥 미연결 처리
            log.debug("LunarCrush 조회 실패 %s", symbol, exc_info=True)
            return None
        return parse_social(data)


def make_social_provider(client: "LunarCrushClient"):
    """라이브 social provider — 상장 심볼로 LunarCrush 소셜 지표 조회."""
    def provider(listing) -> dict | None:
        syms = getattr(listing, "symbols", None) or []
        return client.social_for(syms[0]) if syms else None
    return provider
