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
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from ...core.events import Announcement
from ...httpclient import HttpClient
from .base import AnnouncementSource, html_to_text

log = logging.getLogger(__name__)

NOTICE_URL_TMPL = "https://upbit.com/service_center/notice?id={id}"
DETAIL_URL_TMPL = "https://api-manager.upbit.com/api/v1/announcements/{id}"

# api-manager.upbit.com 은 봇 차단(Cloudflare)이 있어 웹 브라우저처럼 Referer/Origin 필요
WEB_HEADERS = {
    "Referer": "https://upbit.com/service_center/notice",
    "Origin": "https://upbit.com",
}


class UpbitSource(AnnouncementSource):
    name = "upbit"

    def __init__(self, url: str, http: HttpClient) -> None:
        self.url = url
        self.http = http

    def fetch(self) -> list[Announcement]:
        payload = self.http.get_json(self.url, headers=WEB_HEADERS)
        return self.parse_payload(payload)

    def fetch_detail(self, ann: Announcement) -> str | None:
        # ⚠️ 상세 응답 스키마(data.body)는 라이브에서 재검증 필요
        try:
            payload = self.http.get_json(
                DETAIL_URL_TMPL.format(id=ann.id), headers=WEB_HEADERS
            )
        except Exception:  # noqa: BLE001
            log.exception("업비트 상세 fetch 실패 id=%s", ann.id)
            return None
        data = payload.get("data", payload) if isinstance(payload, dict) else {}
        body = data.get("body") or data.get("content") or ""
        return html_to_text(body)

    def is_pre_listed(self, symbol: str) -> bool | None:
        """BTC/USDT 마켓이 하루 전 이미 있었나 → KRW만 추가된 기존 코인 여부.
        (api.upbit.com 캔들은 차단 없음. 신규 전체상장은 어제 캔들이 없어 False)"""
        to = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        for q in ("BTC", "USDT"):
            url = (f"https://api.upbit.com/v1/candles/days?market={q}-{symbol}"
                   f"&count=1&to={quote(to)}")
            try:
                rows = self.http.get_json(url)
                if isinstance(rows, list) and rows:
                    return True
            except Exception:  # noqa: BLE001 - 없는 마켓
                pass
        return False

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
