import unittest

from wonsang_bot.core.events import ListingDetected
from wonsang_bot.predictor.features.base import FeatureContext
from wonsang_bot.predictor.features.venue_count import VenueCountFeature, score_for


def _ctx(vc):
    extra = {} if vc is None else {"venue_count": vc}
    return FeatureContext(
        listing=ListingDetected(source="upbit", announcement_id="1", title="t",
                                symbols=["X"], is_krw=True),
        extra=extra,
    )


class TestVenueCountFeature(unittest.TestCase):
    def test_monotonic_buckets(self):
        # 많을수록 높은 점수(데이터: 1개소 위험 → 4+개소 안전)
        self.assertLess(score_for(1), score_for(3))
        self.assertLess(score_for(3), score_for(5))

    def test_single_venue_low(self):
        f = VenueCountFeature(3.0).extract(_ctx(1))
        self.assertTrue(f.available)
        self.assertLess(f.score, 0.4)

    def test_many_venues_high(self):
        f = VenueCountFeature(3.0).extract(_ctx(6))
        self.assertTrue(f.available)
        self.assertGreater(f.score, 0.8)

    def test_missing_unavailable(self):
        self.assertFalse(VenueCountFeature(3.0).extract(_ctx(None)).available)
        self.assertFalse(VenueCountFeature(3.0).extract(_ctx(0)).available)


if __name__ == "__main__":
    unittest.main()
