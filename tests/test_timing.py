import unittest
from datetime import datetime, timedelta, timezone

from wonsang_bot.core.events import ListingDetected
from wonsang_bot.predictor.features.base import FeatureContext
from wonsang_bot.predictor.features.timing import TimingFeature

KST = timezone(timedelta(hours=9))


def _at(dt_kst):
    ev = ListingDetected(source="upbit", announcement_id="1", title="t", symbols=["X"],
                         is_krw=True)
    return FeatureContext(listing=ev, now=dt_kst)


class TestTimingFeature(unittest.TestCase):
    def test_friday_beats_monday(self):
        # 금요일(강) > 월요일(약), 같은 시간대에서
        fri = TimingFeature(1.0).extract(_at(datetime(2025, 10, 24, 14, 0, tzinfo=KST)))
        mon = TimingFeature(1.0).extract(_at(datetime(2025, 10, 20, 14, 0, tzinfo=KST)))
        self.assertGreater(fri.score, mon.score)

    def test_available_and_bounded(self):
        f = TimingFeature(1.0).extract(_at(datetime(2025, 10, 24, 20, 0, tzinfo=KST)))
        self.assertTrue(f.available)
        self.assertGreaterEqual(f.score, 0.0)
        self.assertLessEqual(f.score, 1.0)
        self.assertEqual(f.raw["weekday"], 4)

    def test_afternoon_lower_than_evening_same_day(self):
        aft = TimingFeature(1.0).extract(_at(datetime(2025, 10, 22, 14, 0, tzinfo=KST)))
        eve = TimingFeature(1.0).extract(_at(datetime(2025, 10, 22, 20, 0, tzinfo=KST)))
        self.assertLess(aft.score, eve.score)


if __name__ == "__main__":
    unittest.main()
