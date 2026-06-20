import unittest

from wonsang_bot.collector.archive import fetch_upbit_archive, page_url
from wonsang_bot.collector.assemble import to_raw_case
from wonsang_bot.collector.price import (
    bithumb_candles_to_series,
    upbit_candles_to_series,
)
from wonsang_bot.collector.returns import point_return_pct
from wonsang_bot.core.events import Announcement, Contract
from wonsang_bot.detector.parser import parse_title


class TestPointReturn(unittest.TestCase):
    def test_buy_5min_sell_15min(self):
        # 진입(+300s)=20, 매도(+900s)=24 → +20% (고점 99 는 무시)
        series = [(0, 10), (300, 20), (600, 99), (900, 24), (1200, 30)]
        self.assertAlmostEqual(point_return_pct(series, 0, 300, 900), 20.0)

    def test_not_peak(self):
        # 중간에 급등(+200%)해도 매도시점 가격만 반영
        series = [(300, 10), (600, 30), (900, 9)]
        self.assertAlmostEqual(point_return_pct(series, 0, 300, 900), -10.0)

    def test_fallback_to_nearest(self):
        # 정확한 시점 포인트 없으면 그 이상 첫 포인트 사용
        series = [(310, 10), (920, 13)]
        self.assertAlmostEqual(point_return_pct(series, 0, 300, 900), 30.0)

    def test_empty(self):
        self.assertIsNone(point_return_pct([], 0, 300, 900))


class TestCandleParsers(unittest.TestCase):
    def test_upbit(self):
        rows = [
            {"candle_date_time_utc": "2026-03-01T05:00:00", "trade_price": 1000.0},
            {"candle_date_time_utc": "2026-03-01T05:01:00", "trade_price": 1100.0},
            {"candle_date_time_utc": "bad", "trade_price": 1.0},  # 무시
        ]
        s = upbit_candles_to_series(rows)
        self.assertEqual(len(s), 2)
        self.assertEqual(s[0][1], 1000.0)

    def test_bithumb(self):
        rows = [
            [1740805200000, "100", "110", "120", "95", "3.0"],  # close=110
            [1740805260000, "110", "130", "135", "108", "2.0"],
            ["bad"],  # 무시
        ]
        s = bithumb_candles_to_series(rows)
        self.assertEqual([p for _, p in s], [110.0, 130.0])


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
