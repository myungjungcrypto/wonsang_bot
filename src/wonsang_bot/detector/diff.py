"""신규 공지 디프 — 이미 본 공지 집합과 비교해 새 공지만 골라낸다."""
from __future__ import annotations

from collections.abc import Iterable

from ..core.events import Announcement


def find_new(fetched: Iterable[Announcement], seen_keys: set[str]) -> list[Announcement]:
    """`seen_keys`(=`source:id`)에 없는 공지만, 입력 순서대로 반환."""
    new: list[Announcement] = []
    for ann in fetched:
        if ann.key not in seen_keys:
            new.append(ann)
    return new
