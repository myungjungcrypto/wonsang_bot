import unittest

from wonsang_bot.predictor.labeling import grade_from_return


class TestGradeFromReturn(unittest.TestCase):
    def test_boundaries(self):
        # 대성공 ≥25 / 성공 10~25 / 보통 0~10 / 실패 -10~0 / 큰실패 ≤-10
        self.assertEqual(grade_from_return(50), "대성공")
        self.assertEqual(grade_from_return(25), "대성공")
        self.assertEqual(grade_from_return(24.9), "성공")
        self.assertEqual(grade_from_return(10), "성공")
        self.assertEqual(grade_from_return(9.9), "보통")
        self.assertEqual(grade_from_return(0), "보통")
        self.assertEqual(grade_from_return(-0.1), "실패")
        self.assertEqual(grade_from_return(-10), "실패")
        self.assertEqual(grade_from_return(-10.1), "큰실패")
        self.assertEqual(grade_from_return(-50), "큰실패")

    def test_custom_thresholds(self):
        th = ((50.0, "성공"), (float("-inf"), "실패"))
        self.assertEqual(grade_from_return(60, th), "성공")
        self.assertEqual(grade_from_return(49, th), "실패")


if __name__ == "__main__":
    unittest.main()
