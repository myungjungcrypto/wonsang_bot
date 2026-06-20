import unittest

from wonsang_bot.detector.parser import (
    classify,
    extract_markets,
    extract_symbols,
    parse_title,
)


class TestSymbols(unittest.TestCase):
    def test_nested_paren(self):
        self.assertEqual(extract_symbols("디지털 자산 추가 (메타플래닛(MTP)) (KRW, BTC 마켓)"), ["MTP"])

    def test_simple_paren_with_markets_in_text(self):
        self.assertEqual(extract_symbols("[거래] 무빙(MOVE) KRW, USDT 마켓 디지털 자산 추가"), ["MOVE"])

    def test_quote_currencies_excluded(self):
        # 괄호 안 마켓 목록은 심볼로 잡히면 안 됨
        self.assertEqual(extract_symbols("원화(KRW) 마켓 추가 (디지비(DGB))"), ["DGB"])

    def test_numeric_ticker(self):
        self.assertIn("1INCH", extract_symbols("거래지원 (원인치(1INCH)) (KRW 마켓)"))

    def test_no_symbol(self):
        self.assertEqual(extract_symbols("거래지원 안내드립니다"), [])


class TestMarkets(unittest.TestCase):
    def test_krw_from_hangul(self):
        markets, is_krw = extract_markets("원화 마켓 추가 (이름(SYM))")
        self.assertTrue(is_krw)
        self.assertIn("KRW", markets)

    def test_multi_markets(self):
        markets, is_krw = extract_markets("(SYM) KRW, USDT 마켓 디지털 자산 추가")
        self.assertTrue(is_krw)
        self.assertEqual(markets, ["KRW", "USDT"])

    def test_no_krw(self):
        markets, is_krw = extract_markets("(SYM) USDT 마켓 디지털 자산 추가")
        self.assertFalse(is_krw)


class TestClassify(unittest.TestCase):
    def test_listing(self):
        ok, _ = classify("디지털 자산 추가 (메타플래닛(MTP)) (KRW 마켓)")
        self.assertTrue(ok)

    def test_negative_end_of_support(self):
        ok, _ = classify("거래지원 종료 안내 (ABC)")
        self.assertFalse(ok)

    def test_negative_caution(self):
        ok, _ = classify("유의 종목 지정 안내 (ABC)")
        self.assertFalse(ok)

    def test_unrelated(self):
        ok, _ = classify("서버 점검 안내")
        self.assertFalse(ok)


class TestParseTitle(unittest.TestCase):
    def test_full_krw_listing_high_confidence(self):
        p = parse_title("디지털 자산 추가 (무빙(MOVE)) (KRW, BTC 마켓)")
        self.assertTrue(p.is_listing)
        self.assertEqual(p.symbols, ["MOVE"])
        self.assertTrue(p.is_krw)
        self.assertAlmostEqual(p.confidence, 1.0, places=3)

    def test_end_of_support_not_listing(self):
        p = parse_title("거래지원 종료 안내 (무빙(MOVE)) (KRW 마켓)")
        self.assertFalse(p.is_listing)
        self.assertLess(p.confidence, 0.6)


if __name__ == "__main__":
    unittest.main()
