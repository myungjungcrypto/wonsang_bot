"""감지 서비스 — 폴링 → 디프 → 파싱 → (컨트랙트 해결) → 이벤트 발행.

- 첫 실행 시 기존 공지는 알림 없이 seen 처리(과거 공지 폭탄 방지).
- 각 소스의 fetch는 블로킹이므로 asyncio.to_thread로 감싼다.
"""
from __future__ import annotations

import asyncio
import logging

from ..config import Config
from ..core.bus import EventBus
from ..core.events import Announcement, ListingDetected
from ..resolver.contract import ContractResolver
from ..storage.db import Storage
from .diff import find_new
from .parser import parse_title
from .sources.base import AnnouncementSource

log = logging.getLogger(__name__)


class DetectorService:
    def __init__(
        self,
        config: Config,
        storage: Storage,
        bus: EventBus,
        sources: list[AnnouncementSource],
        resolver: ContractResolver | None = None,
    ) -> None:
        self.config = config
        self.storage = storage
        self.bus = bus
        self.sources = sources
        self.resolver = resolver
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def start(self) -> None:
        if self.config.seed_only_first_run and self.storage.count_seen() == 0:
            await self._seed()
        log.info(
            "감지 시작: sources=%s interval=%.2fs",
            [s.name for s in self.sources],
            self.config.poll_interval_sec,
        )
        while not self._stop.is_set():
            await self.poll_once()
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=self.config.poll_interval_sec
                )
            except asyncio.TimeoutError:
                pass

    async def _seed(self) -> None:
        total = 0
        for src in self.sources:
            try:
                fetched = await asyncio.to_thread(src.fetch)
            except Exception:  # noqa: BLE001
                log.exception("seed fetch 실패: %s", src.name)
                continue
            self.storage.mark_seen_many(fetched)
            total += len(fetched)
        log.info("초기 시딩 완료: 기존 공지 %d건을 seen 처리(알림 없음)", total)

    async def poll_once(self) -> list[ListingDetected]:
        results: list[ListingDetected] = []
        seen = self.storage.seen_keys()
        for src in self.sources:
            try:
                fetched = await asyncio.to_thread(src.fetch)
            except Exception:  # noqa: BLE001
                log.exception("fetch 실패: %s", src.name)
                continue
            for ann in find_new(fetched, seen):
                self.storage.mark_seen(ann)
                seen.add(ann.key)
                ev = await self._handle(ann, src)
                if ev is not None:
                    results.append(ev)
                    await self.bus.publish(ev)
        return results

    async def _handle(
        self, ann: Announcement, src: AnnouncementSource
    ) -> ListingDetected | None:
        parsed = parse_title(ann.title)
        if not parsed.is_listing:
            log.debug("상장 아님(%s): %s [%s]", ann.source, ann.title, parsed.reason)
            return None

        # 상장으로 판단된 건에 한해 본문을 받아 컨트랙트 추출(비용/속도 고려)
        body: str | None = None
        if self.config.fetch_announcement_body:
            try:
                body = await asyncio.to_thread(src.fetch_detail, ann)
            except Exception:  # noqa: BLE001
                log.exception("본문 fetch 실패: %s", ann.key)

        contracts = []
        if self.resolver is not None:
            contracts = self.resolver.resolve(parsed.symbols, ann, body)

        ev = ListingDetected(
            source=ann.source,
            announcement_id=ann.id,
            title=ann.title,
            symbols=parsed.symbols,
            markets=parsed.markets,
            is_krw=parsed.is_krw,
            contracts=contracts,
            url=ann.url,
            published_at=ann.published_at,
            confidence=parsed.confidence,
        )
        self.storage.save_listing(ev)
        log.info(
            "상장 감지! %s %s krw=%s conf=%s",
            ann.source.upper(), parsed.symbols, parsed.is_krw, parsed.confidence,
        )
        return ev
