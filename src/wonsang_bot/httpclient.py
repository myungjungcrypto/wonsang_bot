"""얇은 HTTP 래퍼 (requests 기반).

프록시/타임아웃/UA 주입을 한 곳에서 처리한다.
(EC2 등 해외 IP에서 거래소가 차단할 경우 프록시를 끼워 우회)
"""
from __future__ import annotations

import logging
from typing import Any

import requests

log = logging.getLogger(__name__)


class HttpClient:
    def __init__(
        self,
        timeout: float = 8.0,
        proxy: str | None = None,
        user_agent: str = "Mozilla/5.0 (wonsang_bot)",
    ) -> None:
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )
        if proxy:
            self._session.proxies.update({"http": proxy, "https": proxy})

    def get_json(self, url: str, headers: dict[str, str] | None = None) -> Any:
        resp = self._session.get(url, timeout=self._timeout, headers=headers)
        resp.raise_for_status()
        return resp.json()

    def get_text(self, url: str, headers: dict[str, str] | None = None) -> str:
        resp = self._session.get(url, timeout=self._timeout, headers=headers)
        resp.raise_for_status()
        return resp.text

    def post_json(
        self, url: str, payload: dict[str, Any], headers: dict[str, str] | None = None
    ) -> Any:
        resp = self._session.post(url, json=payload, timeout=self._timeout, headers=headers)
        resp.raise_for_status()
        return resp.json()
