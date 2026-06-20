"""빗썸 공지 소스.

⚠️ 빗썸 공지 엔드포인트/스키마는 변동이 잦고 공식 JSON 안정성이 낮다.
   라이브에서 반드시 재검증하고, 필요시 HTML 파싱 폴백을 구현할 것(TODO).
   본 파서는 흔한 JSON 형태를 관용적으로 처리한다:
     - 최상위 또는 data 아래의 list/notices/notice 배열
     - 각 항목: id|seq|num, title|subject, published_at|created_at|date,
       categories|category
"""
from __future__ import annotations

from typing import Any

from ...core.events import Announcement
from ...httpclient import HttpClient
from .base import AnnouncementSource

# 공지 상세 URL 템플릿(라이브 확인 후 조정)
NOTICE_URL_TMPL = "https://feed.bithumb.com/notice/{id}"


def _first(item: dict, keys: tuple[str, ...]) -> Any:
    for k in keys:
        if k in item and item[k] not in (None, ""):
            return item[k]
    return None


class BithumbSource(AnnouncementSource):
    name = "bithumb"

    def __init__(self, url: str, http: HttpClient) -> None:
        self.url = url
        self.http = http

    def fetch(self) -> list[Announcement]:
        payload = self.http.get_json(self.url)
        return self.parse_payload(payload)

    @staticmethod
    def parse_payload(payload: Any) -> list[Announcement]:
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            data = payload.get("data", payload)
            if isinstance(data, list):
                items = data
            else:
                items = (
                    data.get("list")
                    or data.get("notices")
                    or data.get("notice")
                    or []
                )
        else:
            items = []

        out: list[Announcement] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            aid = _first(it, ("id", "seq", "num", "notice_id"))
            if aid is None:
                continue
            aid = str(aid).strip()
            title = _first(it, ("title", "subject", "name")) or ""
            ts = _first(it, ("published_at", "created_at", "date", "reg_date"))
            cat = _first(it, ("category", "categories", "type"))
            out.append(
                Announcement(
                    source="bithumb",
                    id=aid,
                    title=title,
                    url=NOTICE_URL_TMPL.format(id=aid),
                    category=str(cat) if cat is not None else None,
                    published_at=str(ts) if ts is not None else None,
                    raw=it,
                )
            )
        return out
