import unittest

from wonsang_bot.collector.dex import parse_ohlcv, parse_pools
from wonsang_bot.collector.exchanges import select_buy_venue


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


class TestAnchorSelection(unittest.TestCase):
    def test_dex_anchor_excludes_cex_collision(self):
        # DEX(컨트랙트 검증) 0.17 기준 → mexc 0.37(다른 토큰) 제외, 정상가 채택
        venues = {
            "mexc": {"price": 0.37, "liq": 99999},   # 충돌(고유동성이라도)
            "binance": {"price": 0.171, "liq": 2000},
            "dex": {"price": 0.17, "liq": 50000},
        }
        price, venue, _ = select_buy_venue(venues, anchor_price=0.17)
        self.assertIn(venue, ("dex", "binance"))     # 0.17 근처에서 유동성 최대
        self.assertLess(price, 0.2)

    def test_dex_only_coin(self):
        venues = {"dex": {"price": 0.05, "liq": 30000}}
        price, venue, _ = select_buy_venue(venues, anchor_price=0.05)
        self.assertEqual(venue, "dex")
        self.assertAlmostEqual(price, 0.05)


if __name__ == "__main__":
    unittest.main()
