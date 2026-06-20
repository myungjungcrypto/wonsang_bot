import unittest

from wonsang_bot.core.events import Contract
from wonsang_bot.resolver.contract import (
    merge_contracts,
    pick_coin,
    platforms_to_contracts,
)

A40 = "a" * 40


class TestPickCoin(unittest.TestCase):
    def test_exact_symbol_then_best_rank(self):
        coins = [
            {"id": "foo", "symbol": "abc", "market_cap_rank": 500},
            {"id": "bar", "symbol": "ABC", "market_cap_rank": 50},
            {"id": "baz", "symbol": "abc", "market_cap_rank": None},
        ]
        self.assertEqual(pick_coin(coins, "ABC")["id"], "bar")

    def test_no_exact_uses_best_rank(self):
        coins = [
            {"id": "x", "symbol": "zzz", "market_cap_rank": 80},
            {"id": "y", "symbol": "yyy", "market_cap_rank": 10},
        ]
        self.assertEqual(pick_coin(coins, "ABC")["id"], "y")

    def test_empty(self):
        self.assertIsNone(pick_coin([], "ABC"))


class TestPlatforms(unittest.TestCase):
    def test_maps_and_skips_empty(self):
        cs = platforms_to_contracts(
            {"binance-smart-chain": "0xabc", "ethereum": "0xdef", "": "", "solana": ""}
        )
        self.assertEqual({c.chain for c in cs}, {"bsc", "ethereum"})


class TestMerge(unittest.TestCase):
    def test_cross_validation_promotes_via_and_specific_chain(self):
        addr = "0x" + A40
        body = [Contract(chain="evm", address=addr, via="announcement_body")]
        cg = [Contract(chain="ethereum", address=addr.upper(), via="coingecko")]
        merged = merge_contracts(body, cg)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].chain, "ethereum")  # 구체 체인이 evm 이김
        self.assertEqual(merged[0].via, "body+coingecko")

    def test_distinct_addresses_kept(self):
        merged = merge_contracts(
            [Contract("ethereum", "0x" + A40, "announcement_body")],
            [Contract("solana", "SoLaddr", "coingecko")],
        )
        self.assertEqual(len(merged), 2)


if __name__ == "__main__":
    unittest.main()
