import unittest

from wonsang_bot.collector.lunarcrush import (
    LunarCrushClient,
    make_social_provider,
    parse_social,
)
from wonsang_bot.core.events import ListingDetected
from wonsang_bot.predictor.features.base import FeatureContext
from wonsang_bot.predictor.features.social import SocialFeature


class _Cfg:
    lunarcrush_base_url = "https://lunarcrush.com/api4"
    lunarcrush_api_key = "k"


class _FakeHttp:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def get_json(self, url, headers=None):
        self.calls += 1
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class TestParseSocial(unittest.TestCase):
    def test_dict_data(self):
        out = parse_social({"data": {"galaxy_score": 70, "interactions_24h": 2400}})
        self.assertEqual(out["galaxy_score"], 70.0)
        self.assertEqual(out["interactions_24h"], 2400.0)
        self.assertEqual(out["mentions_per_hour"], 100.0)

    def test_list_data(self):
        out = parse_social({"data": [{"galaxy_score": 50}]})
        self.assertEqual(out["galaxy_score"], 50.0)

    def test_empty_none(self):
        self.assertIsNone(parse_social({}))
        self.assertIsNone(parse_social({"data": {}}))
        self.assertIsNone(parse_social(None))


class TestClientAndProvider(unittest.TestCase):
    def test_social_for_no_key(self):
        cfg = _Cfg()
        cfg.lunarcrush_api_key = None
        c = LunarCrushClient(cfg, _FakeHttp({"data": {"galaxy_score": 9}}))
        self.assertIsNone(c.social_for("X"))

    def test_provider_uses_first_symbol(self):
        c = LunarCrushClient(_Cfg(), _FakeHttp({"data": {"galaxy_score": 80}}))
        provider = make_social_provider(c)
        listing = ListingDetected(source="upbit", announcement_id="1", title="t",
                                  symbols=["ABC"], is_krw=True)
        self.assertEqual(provider(listing), {"galaxy_score": 80.0})

    def test_failure_returns_none(self):
        c = LunarCrushClient(_Cfg(), _FakeHttp(RuntimeError("429")))
        self.assertIsNone(c.social_for("X"))


class TestSocialFeature(unittest.TestCase):
    def test_galaxy_score_preferred(self):
        ctx = FeatureContext(
            listing=ListingDetected(source="upbit", announcement_id="1", title="t",
                                    symbols=["X"], is_krw=True),
            social_provider=lambda ev: {"galaxy_score": 80, "mentions_per_hour": 0},
        )
        f = SocialFeature(1.0).extract(ctx)
        self.assertTrue(f.available)
        self.assertAlmostEqual(f.score, 0.8)

    def test_mentions_fallback(self):
        ctx = FeatureContext(
            listing=ListingDetected(source="upbit", announcement_id="1", title="t",
                                    symbols=["X"], is_krw=True),
            social_provider=lambda ev: {"mentions_per_hour": 100},
        )
        f = SocialFeature(1.0).extract(ctx)
        self.assertTrue(f.available)
        self.assertAlmostEqual(f.score, 0.5)  # 100/200

    def test_unavailable_when_no_provider(self):
        ctx = FeatureContext(
            listing=ListingDetected(source="upbit", announcement_id="1", title="t",
                                    symbols=["X"], is_krw=True))
        self.assertFalse(SocialFeature(1.0).extract(ctx).available)


if __name__ == "__main__":
    unittest.main()
