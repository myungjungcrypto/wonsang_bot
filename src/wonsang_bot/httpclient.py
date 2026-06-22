"""얇은 HTTP 래퍼 (requests 기반).

프록시/타임아웃/UA + 요청간격 제한(throttle) + 429/5xx 백오프 재시도를 한 곳에서 처리.
- min_interval: 요청 사이 최소 간격(초). 거래소 레이트리밋(예: 업비트 10req/s) 회피용.
- max_retries: 429/5xx 시 지수 백오프로 재시도(Retry-After 헤더 우선).
- cache_dir: 설정 시 GET 응답을 URL 기준 디스크 캐시(불변 과거데이터 백필용 — 재실행 가속).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
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
        cache_dir: str | None = None,
    ) -> None:
        self._timeout = timeout
        self._min_interval = min_interval
        self._max_retries = max_retries
        self._backoff = backoff
        self._last = 0.0
        self._cache_dir = cache_dir
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
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

    def _cache_path(self, url: str, ext: str) -> str | None:
        if not self._cache_dir:
            return None
        key = hashlib.sha1(url.encode("utf-8")).hexdigest()
        return os.path.join(self._cache_dir, f"{key}.{ext}")

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
                delay = self._backoff * (2 ** attempt)
                ra = resp.headers.get("Retry-After")
                if ra and ra.replace(".", "", 1).isdigit():
                    delay = max(delay, float(ra))  # Retry-After 가 더 길면 그걸로
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
        path = self._cache_path(url, "json")
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    return json.load(fh)
            except Exception:  # noqa: BLE001 - 캐시 손상 시 재요청
                pass
        data = self._send("GET", url, headers=headers).json()
        if path:
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, ensure_ascii=False)
            except Exception:  # noqa: BLE001 - 캐시 저장 실패는 무시
                pass
        return data

    def get_text(self, url: str, headers: dict[str, str] | None = None) -> str:
        path = self._cache_path(url, "txt")
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    return fh.read()
            except Exception:  # noqa: BLE001
                pass
        text = self._send("GET", url, headers=headers).text
        if path:
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(text)
            except Exception:  # noqa: BLE001
                pass
        return text

    def post_json(
        self, url: str, payload: dict[str, Any], headers: dict[str, str] | None = None
    ) -> Any:
        return self._send("POST", url, json=payload, headers=headers).json()
