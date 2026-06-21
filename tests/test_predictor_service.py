import asyncio
import unittest

from wonsang_bot.config import Config
from wonsang_bot.core.bus import EventBus
from wonsang_bot.core.events import Contract, GRADES, GradePredicted, ListingDetected
from wonsang_bot.predictor.features import build_extractors
from wonsang_bot.predictor.service import PredictorService
from wonsang_bot.storage.db import Storage


def sample_listing():
    return ListingDetected(
        source="upbit",
        announcement_id="1",
        title="AI 에이전트 (NRL) 디지털 자산 추가",
        symbols=["NRL"],
        markets=["KRW"],
        is_krw=True,
        contracts=[Contract("ethereum", "0x" + "a" * 40, "announcement_body")],
    )


class TestPredict(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.storage = Storage(":memory:")
        self.bus = EventBus()
        self.svc = PredictorService(
            self.config, self.storage, self.bus, build_extractors(self.config)
        )

    def tearDown(self):
        self.storage.close()

    def test_predict_shape(self):
        pred = self.svc.predict(sample_listing())
        self.assertIn(pred.grade, GRADES)
        self.assertGreaterEqual(pred.score, 0.0)
        self.assertLessEqual(pred.score, 1.0)
        self.assertEqual(len(pred.features), 6)
        # marketcap/social/listing_type(pre_listed=None) 미가용 → 가용 3개(timing/narrative/supply)
        # conf = (1+1.5+2) / (1+1.5+2+2.5+2.5+1) = 4.5/10.5
        self.assertAlmostEqual(pred.confidence, 4.5 / 10.5, places=3)
        avail = [f for f in pred.features if f.available]
        self.assertEqual(len(avail), 3)

    def test_on_listing_publishes_and_saves(self):
        captured = []

        async def cap(ev):
            captured.append(ev)

        self.bus.subscribe(GradePredicted, cap)
        asyncio.run(self.svc.on_listing(sample_listing()))

        self.assertEqual(len(captured), 1)
        self.assertIsInstance(captured[0], GradePredicted)
        row = self.storage._conn.execute(
            "SELECT grade FROM predictions WHERE announcement_id='1'"
        ).fetchone()
        self.assertIsNotNone(row)


if __name__ == "__main__":
    unittest.main()
