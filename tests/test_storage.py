import unittest

from wonsang_bot.core.events import Announcement, ListingDetected
from wonsang_bot.storage.db import Storage


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.s = Storage(":memory:")

    def tearDown(self):
        self.s.close()

    def test_seen_roundtrip(self):
        a = Announcement(source="upbit", id="100", title="hi")
        self.assertFalse(self.s.is_seen("upbit", "100"))
        self.s.mark_seen(a)
        self.assertTrue(self.s.is_seen("upbit", "100"))
        self.assertEqual(self.s.count_seen("upbit"), 1)

    def test_seen_keys(self):
        self.s.mark_seen_many([
            Announcement(source="upbit", id="1", title="a"),
            Announcement(source="bithumb", id="2", title="b"),
        ])
        self.assertEqual(self.s.seen_keys(), {"upbit:1", "bithumb:2"})

    def test_mark_seen_idempotent(self):
        a = Announcement(source="upbit", id="1", title="a")
        self.s.mark_seen(a)
        self.s.mark_seen(a)
        self.assertEqual(self.s.count_seen(), 1)

    def test_save_listing(self):
        ev = ListingDetected(
            source="upbit", announcement_id="1", title="디지털 자산 추가 (무빙(MOVE)) (KRW 마켓)",
            symbols=["MOVE"], markets=["KRW"], is_krw=True, confidence=1.0,
        )
        self.s.save_listing(ev)
        # 중복 저장(REPLACE)도 에러 없이 동작
        self.s.save_listing(ev)

    def test_clear_cases(self):
        self.s.add_case({"id": "a", "symbol": "A", "grade": "보통", "features": {}})
        self.s.add_case({"id": "b", "symbol": "B", "grade": "성공", "features": {}})
        self.assertEqual(len(self.s.load_cases()), 2)
        removed = self.s.clear_cases()
        self.assertEqual(removed, 2)
        self.assertEqual(self.s.load_cases(), [])


if __name__ == "__main__":
    unittest.main()
