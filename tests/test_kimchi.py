import unittest

from wonsang_bot.collector.binance import parse_klines
from wonsang_bot.collector.kimchi import kimchi_return_pct


class TestKimchiReturn(unittest.TestCase):
    def test_premium(self):
        # 해외 매수 1.0 USDT, 업비트 상장 1500원, 환율 1300원/USDT
        # → 업비트 USDT환산 1500/1300=1.1538 → +15.38%
        r = kimchi_return_pct(usd_buy=1.0, krw_sell=1500.0, usdt_krw=1300.0)
        self.assertAlmostEqual(r, 15.38, places=2)

    def test_loss(self):
        # 해외 1.2, 업비트 1300/1300=1.0 → -16.67%
        r = kimchi_return_pct(usd_buy=1.2, krw_sell=1300.0, usdt_krw=1300.0)
        self.assertAlmostEqual(r, -16.67, places=2)

    def test_missing_inputs(self):
        self.assertIsNone(kimchi_return_pct(None, 1500, 1300))
        self.assertIsNone(kimchi_return_pct(1.0, None, 1300))
        self.assertIsNone(kimchi_return_pct(1.0, 1500, None))
        self.assertIsNone(kimchi_return_pct(0, 1500, 1300))


class TestBinanceParse(unittest.TestCase):
    def test_parse_klines(self):
        rows = [
            [1700000000000, "1.0", "1.2", "0.9", "1.1", "100", 1700000059999],
            [1700000060000, "1.1", "1.3", "1.0", "1.25", "80", 1700000119999],
            ["bad"],  # 무시
        ]
        s = parse_klines(rows)
        self.assertEqual(s, [(1700000000.0, 1.1), (1700000060.0, 1.25)])

    def test_empty(self):
        self.assertEqual(parse_klines([]), [])
        self.assertEqual(parse_klines(None), [])


if __name__ == "__main__":
    unittest.main()
