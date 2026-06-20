"""업비트 공지 소스.

엔드포인트(예): https://api-manager.upbit.com/api/v1/announcements
  ?os=web&page=1&per_page=20&category=trade

⚠️ 응답 스키마는 라이브에서 재검증 필요. 신/구 버전을 모두 시도:
  - data.notices[]  (신)
  - data.list[]     (구)
각 항목: id, title, category, listed_at|first_listed_at|created_at
"""
from __future__ import annotations

import logging

from ...core.events import Announcement
from ...httpclient import HttpClient
from .base import AnnouncementSource, html_to_text

log = logging.getLogger(__name__)

NOTICE_URL_TMPL = "https://upbit.com/service_center/notice?id={id}"
DETAIL_URL_TMPL = "https://api-manager.upbit.com/api/v1/announcements/{id}"


class UpbitSource(AnnouncementSource):
    name = "upbit"

    def __init__(self, url: str, http: HttpClient) -> None:
        self.url = url
        self.http = http

    def fetch(self) -> list[Announcement]:
        payload = self.http.get_json(self.url)
        return self.parse_payload(payload)

    def fetch_detail(self, ann: Announcement) -> str | None:
        # ⚠️ 상세 응답 스키마(data.body)는 라이브에서 재검증 필요
        try:
            payload = self.http.get_json(DETAIL_URL_TMPL.format(id=ann.id))
        except Exception:  # noqa: BLE001
            log.exception("업비트 상세 fetch 실패 id=%s", ann.id)
            return None
        data = payload.get("data", payload) if isinstance(payload, dict) else {}
        body = data.get("body") or data.get("content") or ""
        return html_to_text(body)

    @staticmethod
    def parse_payload(payload: dict) -> list[Announcement]:
        data = payload.get("data", payload) if isinstance(payload, dict) else {}
        items = data.get("notices") or data.get("list") or []
        out: list[Announcement] = []
        for it in items:
            aid = str(it.get("id", "")).strip()
            if not aid:
                continue
            ts = it.get("listed_at") or it.get("first_listed_at") or it.get("created_at")
            out.append(
                Announcement(
                    source="upbit",
                    id=aid,
                    title=it.get("title", ""),
                    url=NOTICE_URL_TMPL.format(id=aid),
                    category=it.get("category"),
                    published_at=ts,
                    raw=it,
                )
            )
        return out
