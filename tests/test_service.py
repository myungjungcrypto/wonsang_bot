import asyncio
import unittest

from wonsang_bot.config import Config
from wonsang_bot.core.bus import EventBus
from wonsang_bot.core.events import Announcement, ListingDetected
from wonsang_bot.detector.service import DetectorService
from wonsang_bot.detector.sources.base import AnnouncementSource
from wonsang_bot.httpclient import HttpClient
from wonsang_bot.resolver.contract import ContractResolver
from wonsang_bot.storage.db import Storage


class FakeSource(AnnouncementSource):
    def __init__(self, name, anns, body=None):
        self.name = name
        self._anns = anns
        self._body = body

    def fetch(self):
        return list(self._anns)

    def fetch_detail(self, ann):
        return self._body


def _bus_with_capture():
    bus = EventBus()
    captured: list[ListingDetected] = []

    async def handler(ev):
        captured.append(ev)

    bus.subscribe(ListingDetected, handler)
    return bus, captured


class TestService(unittest.TestCase):
    def test_detects_krw_listing_filters_noise_and_dedups(self):
        anns = [
            Announcement("upbit", "1", "디지털 자산 추가 (무빙(MOVE)) (KRW 마켓)"),
            Announcement("upbit", "2", "거래지원 종료 안내 (올드(OLD)) (KRW 마켓)"),
            Announcement("upbit", "3", "[안내] 시스템 점검 예정"),
        ]
        cfg = Config(seed_only_first_run=False)
        storage = Storage(":memory:")
        bus, captured = _bus_with_capture()
        svc = DetectorService(cfg, storage, bus, [FakeSource("upbit", anns)], resolver=None)

        res = asyncio.run(svc.poll_once())
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].symbols, ["MOVE"])
        self.assertTrue(res[0].is_krw)
        self.assertEqual(len(captured), 1)

        # 같은 공지 재폴링 → 신규 없음(중복 알림 방지)
        self.assertEqual(asyncio.run(svc.poll_once()), [])
        self.assertEqual(len(captured), 1)
        storage.close()

    def test_contract_extracted_from_body_into_event(self):
        addr = "0x" + "a" * 40
        anns = [Announcement("upbit", "1", "디지털 자산 추가 (무빙(MOVE)) (KRW 마켓)")]
        cfg = Config(seed_only_first_run=False, coingecko_enabled=False)
        storage = Storage(":memory:")
        bus, captured = _bus_with_capture()
        resolver = ContractResolver(cfg, HttpClient())  # coingecko off → 네트워크 호출 없음
        src = FakeSource("upbit", anns, body=f"네트워크: 이더리움(ERC-20) 컨트랙트 {addr}")
        svc = DetectorService(cfg, storage, bus, [src], resolver=resolver)

        res = asyncio.run(svc.poll_once())
        self.assertEqual(len(res), 1)
        self.assertEqual(len(res[0].contracts), 1)
        self.assertEqual(res[0].contracts[0].chain, "ethereum")
        self.assertEqual(res[0].contracts[0].address.lower(), addr)
        self.assertEqual(len(captured), 1)
        storage.close()

    def test_seed_marks_seen_without_emitting(self):
        anns = [Announcement("upbit", "1", "디지털 자산 추가 (무빙(MOVE)) (KRW 마켓)")]
        cfg = Config(seed_only_first_run=True)
        storage = Storage(":memory:")
        bus, captured = _bus_with_capture()
        svc = DetectorService(cfg, storage, bus, [FakeSource("upbit", anns)])

        asyncio.run(svc._seed())
        self.assertEqual(storage.count_seen(), 1)
        self.assertEqual(asyncio.run(svc.poll_once()), [])
        self.assertEqual(captured, [])
        storage.close()


if __name__ == "__main__":
    unittest.main()
