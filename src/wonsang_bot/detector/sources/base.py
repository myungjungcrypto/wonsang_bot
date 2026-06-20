"""공지 소스 인터페이스."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ...core.events import Announcement


class AnnouncementSource(ABC):
    name: str = "base"

    @abstractmethod
    def fetch(self) -> list[Announcement]:
        """현재 공지 목록을 가져온다(블로킹). 실패 시 예외 발생 가능."""
        raise NotImplementedError
