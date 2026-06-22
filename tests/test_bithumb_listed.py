import unittest

from wonsang_bot.core.events import ListingDetected
from wonsang_bot.predictor.features.base import FeatureContext
from wonsang_bot.predictor.features.bithumb_listed import BithumbListedFeature


def _ctx(pre):
    return FeatureContext(listing=ListingDetected(
        source="upbit", announcement_id="1", title="t", symbols=["X"],
        is_krw=True, pre_listed_bithumb=pre,
    ))


class TestBithumbListedFeature(unittest.TestCase):
    def test_on_bithumb_lower_than_not(self):
        on = BithumbListedFeature(1.0).extract(_ctx(True))
        off = BithumbListedFeature(1.0).extract(_ctx(False))
        self.assertTrue(on.available)
        self.assertTrue(off.available)
        self.assertLess(on.score, off.score)   # 가설: 빗썸 선상장이 약간 낮음

    def test_unknown_unavailable(self):
        self.assertFalse(BithumbListedFeature(1.0).extract(_ctx(None)).available)


class TestBithumbPreListed(unittest.TestCase):
    def test_helper_true_false_none(self):
        from wonsang_bot.detector.sources.bithumb import bithumb_pre_listed

        class _Http:
            def __init__(self, rows):
                self._rows = rows

            def get_json(self, url, headers=None):
                if isinstance(self._rows, Exception):
                    raise self._rows
                return self._rows

        self.assertIs(bithumb_pre_listed(_Http([{"x": 1}]), "AAA"), True)
        self.assertIs(bithumb_pre_listed(_Http([]), "AAA"), False)
        self.assertIsNone(bithumb_pre_listed(_Http(RuntimeError("404")), "AAA"))


if __name__ == "__main__":
    unittest.main()
