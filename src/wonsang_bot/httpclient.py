"""얇은 HTTP 래퍼 (requests 기반).

프록시/타임아웃/UA + 요청간격 제한(throttle) + 429/5xx 백오프 재시도를 한 곳에서 처리.
- min_interval: 요청 사이 최소 간격(초). 거래소 레이트리밋(예: 업비트 10req/s) 회피용.
- max_retries: 429/5xx 시 지수 백오프로 재시도(Retry-After 헤더 우선).
"""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

log = logging.getLogger(__name__)

_RETRY_STATUS = {429, 500, 502, 503, 504}


class HttpClient:
    def __init__(
        self,
        timeout: float = 8.0,
        proxy: str | None = None,
        user_agent: str = "Mozilla/5.0 (wonsang_bot)",
        min_interval: float = 0.0,
        max_retries: int = 2,
        backoff: float = 0.5,
    ) -> None:
        self._timeout = timeout
        self._min_interval = min_interval
        self._max_retries = max_retries
        self._backoff = backoff
        self._last = 0.0
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

    def _throttle(self) -> None:
        if self._min_interval > 0:
            wait = self._min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()

    def _send(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        for attempt in range(self._max_retries + 1):
            self._throttle()
            resp = self._session.request(method, url, timeout=self._timeout, **kwargs)
            if resp.status_code in _RETRY_STATUS and attempt < self._max_retries:
                ra = resp.headers.get("Retry-After")
                delay = (
                    float(ra) if ra and ra.replace(".", "", 1).isdigit()
                    else self._backoff * (2 ** attempt)
                )
                log.warning("HTTP %s → %ss 후 재시도(%d/%d): %s",
                            resp.status_code, round(delay, 2), attempt + 1,
                            self._max_retries, url)
                time.sleep(delay)
                continue
            resp.raise_for_status()
            return resp
        resp.raise_for_status()  # 마지막 시도도 실패 시 예외
        return resp

    def get_json(self, url: str, headers: dict[str, str] | None = None) -> Any:
        return self._send("GET", url, headers=headers).json()

    def get_text(self, url: str, headers: dict[str, str] | None = None) -> str:
        return self._send("GET", url, headers=headers).text

    def post_json(
        self, url: str, payload: dict[str, Any], headers: dict[str, str] | None = None
    ) -> Any:
        return self._send("POST", url, json=payload, headers=headers).json()
