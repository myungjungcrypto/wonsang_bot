import unittest

from wonsang_bot.collector.dex import parse_ohlcv, parse_pools


class TestDexParsers(unittest.TestCase):
    def test_parse_pools_sorted_by_liquidity(self):
        payload = {"data": [
            {"attributes": {"address": "0xpoolA", "reserve_in_usd": "1000"}},
            {"attributes": {"address": "0xpoolB", "reserve_in_usd": "9000"}},
            {"attributes": {"address": None, "reserve_in_usd": "5"}},  # 무시
        ]}
        pools = parse_pools(payload)
        self.assertEqual(pools[0], ("0xpoolB", 9000.0))  # 유동성 최대 먼저
        self.assertEqual(len(pools), 2)

    def test_parse_ohlcv(self):
        payload = {"data": {"attributes": {"ohlcv_list": [
            [1700000060, 1.0, 1.2, 0.9, 1.15, 500],
            [1700000000, 0.9, 1.0, 0.8, 1.0, 400],
        ]}}}
        s = parse_ohlcv(payload)
        self.assertEqual(sorted(s), [(1700000000.0, 1.0), (1700000060.0, 1.15)])

    def test_empty(self):
        self.assertEqual(parse_pools({}), [])
        self.assertEqual(parse_ohlcv(None), [])


if __name__ == "__main__":
    unittest.main()
