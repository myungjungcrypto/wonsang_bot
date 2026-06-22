import unittest

from wonsang_bot.collector.analysis import _when, summarize


class TestWhen(unittest.TestCase):
    def test_kst_weekday_and_daypart(self):
        # 2025-10-20T09:30:00+09:00 = 월요일 오전
        wd, part = _when({"listed_at": "2025-10-20T09:30:00+09:00"})
        self.assertEqual(wd, "월")
        self.assertEqual(part, "오전(6-12)")

    def test_utc_converted_to_kst(self):
        # 2025-10-20T20:00:00Z = KST 익일 05:00 → 화 심야
        wd, part = _when({"listed_at": "2025-10-20T20:00:00Z"})
        self.assertEqual(wd, "화")
        self.assertEqual(part, "심야(0-6)")

    def test_missing_or_bad(self):
        self.assertEqual(_when({}), (None, None))
        self.assertEqual(_when({"listed_at": "nope"}), (None, None))


class TestSummarizeTime(unittest.TestCase):
    def test_buckets_by_weekday_and_daypart(self):
        cases = [
            {"realized_return_pct": 10, "listed_at": "2025-10-20T20:00:00+09:00"},  # 월 저녁
            {"realized_return_pct": -5, "listed_at": "2025-10-25T14:00:00+09:00"},  # 토 오후
        ]
        s = summarize(cases)
        self.assertEqual(s["by_weekday"]["월"]["n"], 1)
        self.assertEqual(s["by_weekday"]["토"]["n"], 1)
        self.assertEqual(s["by_daypart"]["저녁(17-24)"]["n"], 1)
        self.assertEqual(s["by_daypart"]["오후(12-17)"]["n"], 1)


if __name__ == "__main__":
    unittest.main()
