import unittest

from wonsang_bot.core.events import Contract, FeatureScore, GradePredicted, ListingDetected
from wonsang_bot.notify.telegram import TelegramNotifier


class TestFormatListing(unittest.TestCase):
    def test_escapes_special_chars_in_title(self):
        # 제목에 < > & _ * [ 가 있어도 HTML 안전(파싱 400 방지)
        ev = ListingDetected(
            source="upbit", announcement_id="1",
            title="A_B <b>x</b> & [pump] *100%*", symbols=["A_B"], markets=["KRW"],
            is_krw=True, contracts=[Contract(chain="ethereum", address="0x<&>")],
        )
        out = TelegramNotifier.format_listing(ev)
        self.assertIn("&lt;b&gt;", out)        # < > 이스케이프됨
        self.assertIn("&amp;", out)            # & 이스케이프됨
        self.assertNotIn("<b>x</b>", out)      # 원본 태그가 그대로 새지 않음
        self.assertIn("<b>원화상장 감지</b>", out)  # 의도된 태그는 유지
        self.assertIn("<code>0x&lt;&amp;&gt;</code>", out)

    def test_no_symbols(self):
        ev = ListingDetected(source="bithumb", announcement_id="1", title="t", is_krw=False)
        out = TelegramNotifier.format_listing(ev)
        self.assertIn("상장 공지 감지", out)
        self.assertIn("(심볼 미확인)", out)


class TestFormatGrade(unittest.TestCase):
    def _pred(self, **kw):
        base = dict(source="upbit", announcement_id="1", symbols=["X_Y"], grade="성공",
                    score=0.67, confidence=1.0,
                    features=[FeatureScore(name="timing", score=0.75, weight=1.0,
                                           available=True, detail="KST 금 <test> & 저녁")])
        base.update(kw)
        return GradePredicted(**base)

    def test_escapes_and_shows_buy(self):
        out = TelegramNotifier.format_grade(self._pred(
            buy_venue="dex:bsc", buy_price=0.062, venue_count=5, secondary_grade="대성공"))
        self.assertIn("<b>등급 예측: 성공</b>", out)
        self.assertIn("💰 매수처: dex:bsc $0.062, 5곳", out)
        self.assertIn("&lt;test&gt; &amp; 저녁", out)   # 피처 detail 이스케이프
        self.assertNotIn("<test>", out)

    def test_no_buy_when_missing(self):
        out = TelegramNotifier.format_grade(self._pred())
        self.assertNotIn("💰", out)


if __name__ == "__main__":
    unittest.main()
