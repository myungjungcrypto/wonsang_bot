"""공지 소스 인터페이스 + 공용 유틸."""
from __future__ import annotations

import html as _html
import re
from abc import ABC, abstractmethod

from ...core.events import Announcement

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_WS_RE = re.compile(r"[ \t ]+")


def html_to_text(html: str | None) -> str:
    """HTML 본문 → 평문(공지에서 주소/네트워크 추출용). 순수 함수."""
    if not html:
        return ""
    text = _SCRIPT_STYLE_RE.sub(" ", html)
    text = _TAG_RE.sub(" ", text)
    text = _html.unescape(text)
    text = _WS_RE.sub(" ", text)
    # 빈 줄 정리
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


class AnnouncementSource(ABC):
    name: str = "base"

    @abstractmethod
    def fetch(self) -> list[Announcement]:
        """현재 공지 목록을 가져온다(블로킹). 실패 시 예외 발생 가능."""
        raise NotImplementedError

    def fetch_detail(self, ann: Announcement) -> str | None:
        """공지 본문 평문을 가져온다(컨트랙트 추출용). 기본은 미지원(None)."""
        return None

    def is_pre_listed(self, symbol: str) -> bool | None:
        """KRW만 추가된 기존 코인인가(BTC/USDT 선상장). 미지원이면 None."""
        return None
