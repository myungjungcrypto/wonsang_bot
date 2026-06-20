import unittest
from datetime import datetime, timedelta, timezone

from wonsang_bot.core.events import Contract, ListingDetected
from wonsang_bot.predictor.features.base import FeatureContext
from wonsang_bot.predictor.features.marketcap import (
    MarketCapFeature,
    score_marketcap,
)
from wonsang_bot.predictor.features.narrative import NarrativeFeature, tag_narratives
from wonsang_bot.predictor.features.social import SocialFeature, score_social
from wonsang_bot.predictor.features.supply import SupplyChokeFeature
from wonsang_bot.predictor.features.timing import TimingFeature

KST = timezone(timedelta(hours=9))


def listing(**kw):
    base = dict(source="upbit", announcement_id="1", title="t", symbols=["ABC"])
    base.update(kw)
    return ListingDetected(**base)


class TestTiming(unittest.TestCase):
    def _score_at(self, dt):
        ctx = FeatureContext(listing=listing(), now=dt)
        return TimingFeature(1.0).extract(ctx).score

    def test_friday_evening_beats_tuesday_afternoon(self):
        base = datetime(2026, 6, 1, 20, 0, tzinfo=KST)
        friday = base + timedelta(days=(4 - base.weekday()) % 7)
        tuesday = (base + timedelta(days=(1 - base.weekday()) % 7)).replace(hour=14)
        self.assertEqual(friday.weekday(), 4)
        self.assertEqual(tuesday.weekday(), 1)
        self.assertGreater(self._score_at(friday), self._score_at(tuesday))
        self.assertGreaterEqual(self._score_at(friday), 0.75)


class TestNarrative(unittest.TestCase):
    def test_tagging(self):
        self.assertIn("ai", tag_narratives("AI 에이전트 프로젝트"))
        self.assertIn("meme", tag_narratives("pepe 밈 코인"))

    def test_hot_narrative_high(self):
        ctx = FeatureContext(listing=listing(title="신규 - AI 에이전트", symbols=["NRL"]))
        self.assertAlmostEqual(NarrativeFeature(1.0).extract(ctx).score, 1.0)

    def test_no_narrative_neutral(self):
        ctx = FeatureContext(listing=listing(title="원화 마켓 추가 안내", symbols=["ABC"]))
        self.assertAlmostEqual(NarrativeFeature(1.0).extract(ctx).score, 0.3)


class TestSupply(unittest.TestCase):
    def _score(self, **kw):
        ctx = FeatureContext(listing=listing(**kw))
        return SupplyChokeFeature(1.0).extract(ctx).score

    def test_bithumb_choke_higher_than_upbit(self):
        b = self._score(source="bithumb", is_krw=True, contracts=[Contract("solana", "x")])
        u = self._score(source="upbit", is_krw=True, contracts=[Contract("ethereum", "x")])
        self.assertGreater(b, u)

    def test_unfriendly_chain_increases_choke(self):
        friendly = self._score(source="bithumb", contracts=[Contract("ethereum", "x")])
        unfriendly = self._score(source="bithumb", contracts=[Contract("aptos", "x")])
        self.assertGreater(unfriendly, friendly)


class TestMarketCap(unittest.TestCase):
    def test_unavailable_without_provider(self):
        f = MarketCapFeature(1.0).extract(FeatureContext(listing=listing()))
        self.assertFalse(f.available)

    def test_small_mc_scores_high(self):
        ctx = FeatureContext(
            listing=listing(), market_provider=lambda ev: {"market_cap_usd": 1_000_000}
        )
        self.assertTrue(MarketCapFeature(1.0).extract(ctx).available)
        self.assertAlmostEqual(MarketCapFeature(1.0).extract(ctx).score, 1.0)

    def test_score_bounds(self):
        self.assertAlmostEqual(score_marketcap(2_000_000), 1.0)
        self.assertAlmostEqual(score_marketcap(500_000_000), 0.0)


class TestSocial(unittest.TestCase):
    def test_unavailable_without_provider(self):
        f = SocialFeature(1.0).extract(FeatureContext(listing=listing()))
        self.assertFalse(f.available)

    def test_score_bounds(self):
        self.assertAlmostEqual(score_social(200), 1.0)
        self.assertAlmostEqual(score_social(0), 0.0)


if __name__ == "__main__":
    unittest.main()
