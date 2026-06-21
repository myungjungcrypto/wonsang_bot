import unittest

from wonsang_bot.collector.upbit_market import (
    parse_krw_markets,
    realized_return_from_series,
)


class TestParseMarkets(unittest.TestCase):
    def test_filters_krw_only(self):
        payload = [
            {"market": "KRW-BTC", "korean_name": "비트코인", "english_name": "Bitcoin"},
            {"market": "BTC-ETH", "korean_name": "이더리움", "english_name": "Ethereum"},
            {"market": "KRW-NEWAI", "korean_name": "뉴에이아이", "english_name": "NewAI"},
        ]
        out = parse_krw_markets(payload)
        self.assertEqual([m["symbol"] for m in out], ["BTC", "NEWAI"])
        self.assertEqual(out[0]["market"], "KRW-BTC")
        self.assertIn("비트코인", out[0]["name"])
        self.assertIn("Bitcoin", out[0]["name"])

    def test_empty(self):
        self.assertEqual(parse_krw_markets([]), [])
        self.assertEqual(parse_krw_markets(None), [])


class TestRealizedReturn(unittest.TestCase):
    def test_first_candle_is_listing(self):
        # 첫 체결 t0=1000, +300초=가격20, +900초=가격23 → +15%
        series = [(1000, 10), (1300, 20), (1600, 99), (1900, 23)]
        listing_ts, ret = realized_return_from_series(series, 300, 900)
        self.assertEqual(listing_ts, 1000)
        self.assertAlmostEqual(ret, 15.0)

    def test_empty(self):
        self.assertEqual(realized_return_from_series([], 300, 900), (None, None))


if __name__ == "__main__":
    unittest.main()
