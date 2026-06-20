import math
import unittest

from wonsang_bot.predictor.historical import Case, HistoricalStore, distance


class TestDistance(unittest.TestCase):
    def test_shared_keys(self):
        # 공유키 2개(a,b), 차이는 b에서만 1 → sqrt((0+1)/2)
        d = distance({"a": 0.0, "b": 1.0}, {"a": 0.0, "b": 0.0})
        self.assertAlmostEqual(d, math.sqrt(0.5))

    def test_no_shared_keys_inf(self):
        self.assertTrue(math.isinf(distance({"a": 1.0}, {"b": 1.0})))


class TestNearest(unittest.TestCase):
    def setUp(self):
        self.store = HistoricalStore([
            Case("c1", "AAA", {"timing": 0.8, "narrative": 1.0}, "대성공"),
            Case("c2", "BBB", {"timing": 0.3, "narrative": 0.3}, "큰실패"),
            Case("c3", "CCC", {"unrelated": 0.5}, "보통"),  # 공유키 없음 → 제외
        ])

    def test_nearest_orders_by_distance(self):
        nb = self.store.nearest({"timing": 0.78, "narrative": 0.95}, k=2)
        self.assertEqual([c.id for c, _ in nb], ["c1", "c2"])

    def test_suggest_grade_follows_closest(self):
        nb = self.store.nearest({"timing": 0.8, "narrative": 1.0}, k=2)
        self.assertEqual(self.store.suggest_grade(nb), "대성공")

    def test_suggest_grade_empty(self):
        self.assertIsNone(self.store.suggest_grade([]))

    def test_from_dicts(self):
        store = HistoricalStore.from_dicts([
            {"id": "x", "symbol": "X", "grade": "성공", "features": {"timing": 0.6}},
        ])
        self.assertEqual(store.cases[0].grade, "성공")


if __name__ == "__main__":
    unittest.main()
