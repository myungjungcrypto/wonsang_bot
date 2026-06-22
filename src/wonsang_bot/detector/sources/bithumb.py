"""빗썸 공지 소스.

⚠️ 빗썸 공지 엔드포인트/스키마는 변동이 잦고 공식 JSON 안정성이 낮다.
   라이브에서 반드시 재검증하고, 필요시 HTML 파싱 폴백을 구현할 것(TODO).
   본 파서는 흔한 JSON 형태를 관용적으로 처리한다:
     - 최상위 또는 data 아래의 list/notices/notice 배열
     - 각 항목: id|seq|num, title|subject, published_at|created_at|date,
       categories|category
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from ...core.events import Announcement
from ...httpclient import HttpClient
from .base import AnnouncementSource, html_to_text

log = logging.getLogger(__name__)

# 공지 상세 URL 템플릿(라이브 확인 후 조정)
NOTICE_URL_TMPL = "https://feed.bithumb.com/notice/{id}"
# 빗썸 v1 은 업비트 호환 캔들 API
BITHUMB_CANDLES_URL = "https://api.bithumb.com/v1/candles/days"


def bithumb_pre_listed(http: HttpClient, symbol: str) -> bool | None:
    """빗썸 KRW 마켓 일봉이 하루 전 이미 있었나 → 빗썸 기상장 여부.

    True=빗썸 선상장, False=없음(신규), None=조회 실패(미상).
    (빗썸 v1 은 업비트 호환 — 라이브 재검증 필요)
    """
    to = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    url = f"{BITHUMB_CANDLES_URL}?market=KRW-{symbol}&count=1&to={quote(to)}"
    try:
        rows = http.get_json(url)
    except Exception:  # noqa: BLE001 - 없는 마켓/네트워크 실패는 미상
        log.debug("빗썸 기상장 조회 실패 %s", symbol, exc_info=True)
        return None
    return bool(isinstance(rows, list) and rows)


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

    def fetch_detail(self, ann: Announcement) -> str | None:
        # 빗썸 상세는 HTML 페이지일 가능성이 큼 → 평문화
        url = ann.url or NOTICE_URL_TMPL.format(id=ann.id)
        try:
            html = self.http.get_text(url)
        except Exception:  # noqa: BLE001
            log.exception("빗썸 상세 fetch 실패 id=%s", ann.id)
            return None
        return html_to_text(html)

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
