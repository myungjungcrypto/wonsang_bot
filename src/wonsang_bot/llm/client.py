"""LLM 추상화 — 비활성/교체 가능.

기본은 NullLLM(아무것도 안 함). 설정에서 켜면 ClaudeLLM 사용.
비용 절감을 위해 호출부는 "룰베이스로 모호할 때만" LLM을 부르도록 한다.
나중에 다른 provider를 추가해도 호출부는 그대로 유지된다.
"""
from __future__ import annotations

import logging
from typing import Protocol

from ..config import Config
from ..httpclient import HttpClient

log = logging.getLogger(__name__)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class LLMClient(Protocol):
    enabled: bool

    def complete(self, system: str, prompt: str, max_tokens: int = 1024) -> str | None:
        ...


class NullLLM:
    """LLM 미사용 시 기본 구현."""
    enabled = False

    def complete(self, system: str, prompt: str, max_tokens: int = 1024) -> str | None:
        return None


class ClaudeLLM:
    enabled = True

    def __init__(self, api_key: str, model: str, http: HttpClient) -> None:
        self._key = api_key
        self._model = model
        self._http = http

    def complete(self, system: str, prompt: str, max_tokens: int = 1024) -> str | None:
        headers = {
            "x-api-key": self._key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        payload = {
            "model": self._model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            data = self._http.post_json(ANTHROPIC_URL, payload, headers=headers)
            parts = data.get("content", [])
            return "".join(p.get("text", "") for p in parts if p.get("type") == "text")
        except Exception:  # noqa: BLE001
            log.exception("Claude 호출 실패")
            return None


def get_llm(config: Config, http: HttpClient) -> LLMClient:
    if not config.llm_enabled or not config.llm_api_key:
        return NullLLM()
    if config.llm_provider.lower() == "claude":
        return ClaudeLLM(config.llm_api_key, config.llm_model, http)
    log.warning("알 수 없는 LLM provider=%s → 비활성", config.llm_provider)
    return NullLLM()
