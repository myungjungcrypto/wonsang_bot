import json
import os
import tempfile
import unittest

from wonsang_bot.config import Config
from wonsang_bot.predictor.backfill import (
    RawCase,
    backfill,
    build_case,
    load_raw_cases,
    raw_to_listing,
)
from wonsang_bot.predictor.features import build_extractors
from wonsang_bot.predictor.historical import HistoricalStore
from wonsang_bot.storage.db import Storage


def raw(**kw):
    base = dict(
        id="t:1", symbol="ABC", listed_at="2025-11-21T23:30:00+09:00",
        realized_return_pct=180.0, source="bithumb",
        title="AI 에이전트 원화 마켓 추가",
        contracts=[{"chain": "solana", "address": "x"}],
    )
    base.update(kw)
    return RawCase.from_dict(base)


class TestBuildCase(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.extractors = build_extractors(self.config)

    def test_listing_uses_listed_at(self):
        listing = raw_to_listing(raw())
        self.assertEqual(listing.detected_at, "2025-11-21T23:30:00+09:00")
        self.assertEqual(listing.symbols, ["ABC"])

    def test_offline_features_present_grade_labeled(self):
        case = build_case(raw(), self.extractors, config=self.config)
        # 오프라인 피처는 항상 존재
        for name in ("timing", "narrative", "supply_distribution"):
            self.assertIn(name, case.features)
        # 시총/소셜 스냅샷 없음 → 비활성 → features 에 없음
        self.assertNotIn("marketcap", case.features)
        self.assertNotIn("social", case.features)
        self.assertEqual(case.grade, "대성공")  # 180% → 대성공
        self.assertEqual(case.meta["realized_return_pct"], 180.0)

    def test_snapshot_enables_provider_features(self):
        case = build_case(
            raw(market_cap_usd=1_500_000, mentions_per_hour=160),
            self.extractors, config=self.config,
        )
        self.assertIn("marketcap", case.features)
        self.assertIn("social", case.features)


class TestBackfillRoundtrip(unittest.TestCase):
    def test_backfill_then_nearest(self):
        config = Config()
        storage = Storage(":memory:")
        raws = [
            raw(id="t:win", realized_return_pct=200.0),
            raw(id="t:lose", realized_return_pct=-10.0,
                title="원화 마켓 추가 안내", contracts=[{"chain": "ethereum", "address": "y"}]),
        ]
        n = backfill(raws, build_extractors(config), storage, config=config)
        self.assertEqual(n, 2)

        rows = storage.load_cases()
        self.assertEqual(len(rows), 2)

        store = HistoricalStore.from_dicts(rows)
        # 승리 케이스와 비슷한 피처로 조회 → 가장 가까운 게 대성공이어야
        win = next(c for c in store.cases if c.id == "t:win")
        nb = store.nearest(win.features, k=1)
        self.assertEqual(nb[0][0].grade, "대성공")
        storage.close()


class TestLoad(unittest.TestCase):
    def test_load_wrapper_and_list(self):
        with tempfile.TemporaryDirectory() as d:
            p1 = os.path.join(d, "wrap.json")
            with open(p1, "w", encoding="utf-8") as f:
                json.dump({"note": "x", "cases": [
                    {"id": "a", "symbol": "AA", "listed_at": "2025-01-01T00:00:00+09:00",
                     "realized_return_pct": 10}
                ]}, f)
            p2 = os.path.join(d, "list.json")
            with open(p2, "w", encoding="utf-8") as f:
                json.dump([
                    {"id": "b", "symbol": "BB", "listed_at": "2025-01-01T00:00:00+09:00",
                     "realized_return_pct": 10}
                ], f)
            self.assertEqual(len(load_raw_cases(p1)), 1)
            self.assertEqual(load_raw_cases(p2)[0].symbol, "BB")


if __name__ == "__main__":
    unittest.main()
