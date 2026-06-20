import unittest

from wonsang_bot.core.events import FeatureScore
from wonsang_bot.predictor import scoring


def fs(name, score, weight, available=True):
    return FeatureScore(name=name, score=score, weight=weight, available=available)


class TestCombine(unittest.TestCase):
    def test_weighted_average_over_available(self):
        feats = [fs("a", 1.0, 1.0), fs("b", 0.0, 1.0)]
        score, conf = scoring.combine(feats)
        self.assertAlmostEqual(score, 0.5)
        self.assertAlmostEqual(conf, 1.0)

    def test_unavailable_excluded_lowers_confidence(self):
        feats = [fs("a", 1.0, 1.0), fs("b", 0.0, 3.0, available=False)]
        score, conf = scoring.combine(feats)
        self.assertAlmostEqual(score, 1.0)          # b 제외 → a만
        self.assertAlmostEqual(conf, 1.0 / 4.0)     # 가용 가중치 1 / 전체 4

    def test_none_available(self):
        feats = [fs("a", 1.0, 1.0, available=False)]
        self.assertEqual(scoring.combine(feats), (0.0, 0.0))


class TestToGrade(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(scoring.to_grade(0.95), "대성공")
        self.assertEqual(scoring.to_grade(0.80), "대성공")
        self.assertEqual(scoring.to_grade(0.79), "성공")
        self.assertEqual(scoring.to_grade(0.50), "보통")
        self.assertEqual(scoring.to_grade(0.30), "실패")
        self.assertEqual(scoring.to_grade(0.0), "큰실패")


if __name__ == "__main__":
    unittest.main()
