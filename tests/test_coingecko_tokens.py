import unittest

from wonsang_bot.collector.coingecko import (
    CHAIN_TO_CG_PLATFORM,
    parse_platforms,
)


class TestParsePlatforms(unittest.TestCase):
    def test_maps_all_chains(self):
        payload = {
            "id": "irys",
            "platforms": {
                "ethereum": "0xETH",
                "binance-smart-chain": "0xBSC",
                "solana": "SoLaddr",
                "some-unknown-chain": "0xX",  # 매핑 없으면 제외
            },
        }
        out = parse_platforms(payload)
        self.assertEqual(out["ethereum"], "0xETH")
        self.assertEqual(out["bsc"], "0xBSC")        # binance-smart-chain → bsc
        self.assertEqual(out["solana"], "SoLaddr")
        self.assertNotIn("some-unknown-chain", out)

    def test_empty(self):
        self.assertEqual(parse_platforms({}), {})
        self.assertEqual(parse_platforms(None), {})

    def test_chain_to_platform_inverse(self):
        self.assertEqual(CHAIN_TO_CG_PLATFORM["bsc"], "binance-smart-chain")
        self.assertEqual(CHAIN_TO_CG_PLATFORM["ethereum"], "ethereum")


if __name__ == "__main__":
    unittest.main()
