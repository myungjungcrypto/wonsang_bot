import unittest

from wonsang_bot.predictor.labeling import grade_from_return


class TestGradeFromReturn(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(grade_from_return(250), "대성공")
        self.assertEqual(grade_from_return(100), "대성공")
        self.assertEqual(grade_from_return(99.9), "성공")
        self.assertEqual(grade_from_return(40), "성공")
        self.assertEqual(grade_from_return(20), "보통")
        self.assertEqual(grade_from_return(15), "보통")
        self.assertEqual(grade_from_return(5), "실패")
        self.assertEqual(grade_from_return(0), "실패")
        self.assertEqual(grade_from_return(-0.1), "큰실패")
        self.assertEqual(grade_from_return(-50), "큰실패")

    def test_custom_thresholds(self):
        th = ((50.0, "성공"), (float("-inf"), "실패"))
        self.assertEqual(grade_from_return(60, th), "성공")
        self.assertEqual(grade_from_return(49, th), "실패")


if __name__ == "__main__":
    unittest.main()
