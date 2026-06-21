import unittest

from wonsang_bot.collector.analysis import summarize
from wonsang_bot.core.events import ListingDetected
from wonsang_bot.predictor.features.base import FeatureContext
from wonsang_bot.predictor.features.listing_type import ListingTypeFeature


def _ctx(pre):
    return FeatureContext(listing=ListingDetected(
        source="upbit", announcement_id="1", title="t", symbols=["X"],
        is_krw=True, pre_listed=pre,
    ))


class TestListingTypeFeature(unittest.TestCase):
    def test_pre_listed_low_score(self):
        f = ListingTypeFeature(2.0).extract(_ctx(True))
        self.assertTrue(f.available)
        self.assertLess(f.score, 0.4)

    def test_fresh_high_score(self):
        f = ListingTypeFeature(2.0).extract(_ctx(False))
        self.assertTrue(f.available)
        self.assertGreater(f.score, 0.5)

    def test_unknown_unavailable(self):
        f = ListingTypeFeature(2.0).extract(_ctx(None))
        self.assertFalse(f.available)


class TestSummarize(unittest.TestCase):
    def _case(self, ret, pre, vc):
        return {"realized_return_pct": ret, "pre_listed": pre, "meta": {"venue_count": vc}}

    def test_failure_rate_by_type(self):
        cases = [
            self._case(50, False, 5),    # 신규 성공
            self._case(30, False, 4),    # 신규 성공
            self._case(-20, True, 2),    # KRW만추가 실패
            self._case(-50, True, 1),    # KRW만추가 실패
            self._case(5, True, 1),      # KRW만추가 breakeven
        ]
        s = summarize(cases)
        self.assertEqual(s["by_listing_type"]["신규전체상장"]["fail_rate"], 0.0)
        self.assertEqual(s["by_listing_type"]["KRW만추가(기존코인)"]["n"], 3)
        self.assertAlmostEqual(
            s["by_listing_type"]["KRW만추가(기존코인)"]["fail_rate"], 2 / 3, places=2)
        # 거래소 가용성 버킷
        self.assertEqual(s["by_venue_count"]["1개소"]["n"], 2)
        self.assertEqual(s["by_venue_count"]["4+개소"]["n"], 2)


if __name__ == "__main__":
    unittest.main()
