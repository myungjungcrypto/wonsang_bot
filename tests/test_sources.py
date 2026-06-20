import json
import os
import unittest

from wonsang_bot.detector.sources.bithumb import BithumbSource
from wonsang_bot.detector.sources.upbit import UpbitSource

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def load(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh)


class TestUpbitParse(unittest.TestCase):
    def test_parse(self):
        anns = UpbitSource.parse_payload(load("upbit_announcements.json"))
        self.assertEqual(len(anns), 4)
        first = anns[0]
        self.assertEqual(first.source, "upbit")
        self.assertEqual(first.id, "5001")
        self.assertIn("MOVE", first.title)
        self.assertTrue(first.url.endswith("id=5001"))
        self.assertEqual(first.published_at, "2026-06-19T10:00:00+09:00")

    def test_handles_legacy_list_key(self):
        payload = {"data": {"list": [{"id": 1, "title": "t", "created_at": "x"}]}}
        anns = UpbitSource.parse_payload(payload)
        self.assertEqual(len(anns), 1)
        self.assertEqual(anns[0].id, "1")


class TestBithumbParse(unittest.TestCase):
    def test_parse_tolerant_fields(self):
        anns = BithumbSource.parse_payload(load("bithumb_announcements.json"))
        self.assertEqual(len(anns), 2)
        self.assertEqual(anns[0].id, "9001")
        self.assertEqual(anns[0].source, "bithumb")
        # 두 번째 항목은 seq/subject/categories 키 사용
        self.assertEqual(anns[1].id, "9000")
        self.assertIn("점검", anns[1].title)

    def test_top_level_list(self):
        anns = BithumbSource.parse_payload([{"id": 7, "title": "원화 마켓 추가 (AAA)"}])
        self.assertEqual(len(anns), 1)
        self.assertEqual(anns[0].id, "7")


if __name__ == "__main__":
    unittest.main()
