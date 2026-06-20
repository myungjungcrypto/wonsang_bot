"""아주 단순한 비동기 이벤트 버스(pub/sub).

핸들러 예외는 격리하여 다른 핸들러/루프를 죽이지 않는다.
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

log = logging.getLogger(__name__)

Handler = Callable[[Any], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[type, list[Handler]] = {}

    def subscribe(self, event_type: type, handler: Handler) -> None:
        self._subs.setdefault(event_type, []).append(handler)

    async def publish(self, event: Any) -> None:
        for handler in self._subs.get(type(event), []):
            try:
                await handler(event)
            except Exception:  # noqa: BLE001 - 핸들러 격리
                log.exception("event handler failed for %s", type(event).__name__)
