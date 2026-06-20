import unittest

from wonsang_bot.collector.archive import fetch_upbit_archive, page_url
from wonsang_bot.collector.assemble import to_raw_case
from wonsang_bot.collector.returns import peak_return_pct
from wonsang_bot.core.events import Announcement, Contract
from wonsang_bot.detector.parser import parse_title


class TestReturns(unittest.TestCase):
    def test_peak_within_window(self):
        # 상장 t=100, 진입가 10, 윈도(100~200) 고점 25 → +150%
        series = [(90, 9), (100, 10), (150, 25), (210, 50)]
        self.assertAlmostEqual(peak_return_pct(series, 100, 100), 150.0)

    def test_excludes_outside_window(self):
        series = [(100, 10), (1000, 100)]  # 1000 은 윈도 밖
        self.assertAlmostEqual(peak_return_pct(series, 100, 100), 0.0)

    def test_entry_falls_back_to_last_before(self):
        series = [(50, 20)]  # 상장 이후 포인트 없음 → 마지막 직전값 진입
        self.assertAlmostEqual(peak_return_pct(series, 100, 100), 0.0)

    def test_empty(self):
        self.assertIsNone(peak_return_pct([], 100, 100))


class TestPageUrl(unittest.TestCase):
    def test_replaces_existing_page(self):
        u = "https://x/api?os=web&page=1&per_page=20"
        self.assertEqual(page_url(u, 3), "https://x/api?os=web&page=3&per_page=20")

    def test_adds_when_missing(self):
        self.assertEqual(page_url("https://x/api?os=web", 2), "https://x/api?os=web&page=2")
        self.assertEqual(page_url("https://x/api", 2), "https://x/api?page=2")


class _FakeHttp:
    """page 별 payload 를 돌려주는 가짜 http."""

    def __init__(self, pages):
        self.pages = pages

    def get_json(self, url, headers=None):
        import re
        m = re.search(r"page=(\d+)", url)
        p = int(m.group(1)) if m else 1
        return self.pages.get(p, {"data": {"notices": []}})


class TestArchive(unittest.TestCase):
    def test_paginates_and_dedupes(self):
        pages = {
            1: {"data": {"notices": [{"id": "1", "title": "a"}, {"id": "2", "title": "b"}]}},
            2: {"data": {"notices": [{"id": "2", "title": "b"}, {"id": "3", "title": "c"}]}},
            3: {"data": {"notices": []}},  # 빈 페이지 → 중단
        }
        anns = fetch_upbit_archive(_FakeHttp(pages), "https://x/api?page=1", pages=5)
        self.assertEqual([a.id for a in anns], ["1", "2", "3"])


class TestAssemble(unittest.TestCase):
    def test_to_raw_case(self):
        ann = Announcement(
            source="upbit", id="123",
            title="디지털 자산 추가 (무빙(MOVE)) (KRW 마켓)",
            url="http://u/123", published_at="2025-11-21T23:30:00+09:00",
        )
        parsed = parse_title(ann.title)
        contracts = [Contract("ethereum", "0xabc", "announcement_body")]
        case = to_raw_case(ann, parsed, contracts, 180.0, market_cap_usd=1_500_000)

        self.assertEqual(case["id"], "upbit:123")
        self.assertEqual(case["symbol"], "MOVE")
        self.assertTrue(case["is_krw"])
        self.assertEqual(case["contracts"], [{"chain": "ethereum", "address": "0xabc"}])
        self.assertEqual(case["realized_return_pct"], 180.0)
        self.assertEqual(case["market_cap_usd"], 1_500_000)
        self.assertEqual(case["listed_at"], "2025-11-21T23:30:00+09:00")


if __name__ == "__main__":
    unittest.main()
