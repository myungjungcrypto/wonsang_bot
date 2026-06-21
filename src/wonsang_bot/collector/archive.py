"""과거 공지 아카이브 수집 — 여러 페이지를 훑어 과거 상장 공지를 모은다.

page_url() 은 순수 함수(테스트 가능). 실제 fetch 는 네트워크 의존(라이브 재검증).
"""
from __future__ import annotations

import logging
import re

from ..core.events import Announcement
from ..detector.sources.upbit import WEB_HEADERS, UpbitSource
from ..httpclient import HttpClient

log = logging.getLogger(__name__)


def page_url(base_url: str, page: int) -> str:
    """base_url 의 page 파라미터를 page 값으로 설정/치환."""
    if re.search(r"[?&]page=\d+", base_url):
        return re.sub(r"(?<=[?&]page=)\d+", str(page), base_url)
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}page={page}"


def fetch_upbit_archive(
    http: HttpClient, base_url: str, pages: int = 5
) -> list[Announcement]:
    """업비트 공지 1..pages 페이지를 수집(중복 id 제거)."""
    out: list[Announcement] = []
    seen: set[str] = set()
    for p in range(1, pages + 1):
        try:
            payload = http.get_json(page_url(base_url, p), headers=WEB_HEADERS)
        except Exception:  # noqa: BLE001
            log.exception("아카이브 fetch 실패 page=%s", p)
            break
        anns = UpbitSource.parse_payload(payload)
        if not anns:
            break
        for a in anns:
            if a.key not in seen:
                seen.add(a.key)
                out.append(a)
    return out
