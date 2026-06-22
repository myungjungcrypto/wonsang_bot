import unittest

from wonsang_bot.collector.coingecko import (
    CHAIN_TO_CG_PLATFORM,
    CoinGeckoTokens,
    parse_platforms,
    parse_symbol,
    parse_ticker_exchanges,
)


class _FakeHttp:
    """주소→payload 매핑으로 get_json 흉내."""

    def __init__(self, by_addr: dict[str, dict]) -> None:
        self.by_addr = by_addr

    def get_json(self, url, headers=None):
        for addr, payload in self.by_addr.items():
            if addr.lower() in url.lower():
                return payload
        raise RuntimeError("404")


class _Cfg:
    coingecko_base_url = "https://api.coingecko.com/api/v3"
    coingecko_api_key = ""


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


class TestParseSymbol(unittest.TestCase):
    def test_lowercases_and_strips(self):
        self.assertEqual(parse_symbol({"symbol": " USDS "}), "usds")

    def test_missing_none(self):
        self.assertIsNone(parse_symbol({}))
        self.assertIsNone(parse_symbol(None))
        self.assertIsNone(parse_symbol({"symbol": ""}))


class TestResolve(unittest.TestCase):
    def test_resolve_returns_symbol_and_platforms(self):
        http = _FakeHttp({
            "0xUSDS": {"symbol": "USDS", "platforms": {"ethereum": "0xUSDS",
                                                       "solana": "USDSmint"}},
        })
        cg = CoinGeckoTokens(_Cfg(), http)
        r = cg.resolve("ethereum", "0xUSDS")
        self.assertEqual(r.symbol, "usds")
        self.assertEqual(r.platforms["ethereum"], "0xUSDS")
        self.assertEqual(r.platforms["solana"], "USDSmint")

    def test_resolve_failure_symbol_none(self):
        cg = CoinGeckoTokens(_Cfg(), _FakeHttp({}))
        r = cg.resolve("ethereum", "0xUNKNOWN")
        self.assertIsNone(r.symbol)
        self.assertEqual(r.platforms, {"ethereum": "0xUNKNOWN"})

    def test_pick_right_contract_by_symbol(self):
        # USDS 재현: 공지에 SKY 주소(0xSKY)와 USDS 주소(0xUSDS) 둘 다. 심볼로 USDS 채택.
        http = _FakeHttp({
            "0xSKY": {"id": "sky", "symbol": "SKY", "platforms": {"ethereum": "0xSKY"}},
            "0xUSDS": {"id": "usds", "symbol": "USDS", "platforms": {"ethereum": "0xUSDS"}},
        })
        cg = CoinGeckoTokens(_Cfg(), http)
        self.assertEqual(cg.resolve("ethereum", "0xSKY").symbol, "sky")
        r = cg.resolve("ethereum", "0xUSDS")
        self.assertEqual(r.symbol, "usds")
        self.assertEqual(r.coin_id, "usds")


class TestTickerExchanges(unittest.TestCase):
    def test_maps_market_identifiers_to_ours(self):
        payload = {"tickers": [
            {"market": {"identifier": "binance"}},
            {"market": {"identifier": "bybit_spot"}},   # → bybit
            {"market": {"identifier": "mxc"}},          # → mexc
            {"market": {"identifier": "okex"}},         # → okx
            {"market": {"identifier": "unknown_dex"}},  # 매핑 없음 → 무시
        ]}
        self.assertEqual(parse_ticker_exchanges(payload),
                         {"binance", "bybit", "mexc", "okx"})

    def test_empty(self):
        self.assertEqual(parse_ticker_exchanges({}), set())
        self.assertEqual(parse_ticker_exchanges(None), set())

    def test_exchanges_for_uses_tickers(self):
        http = _FakeHttp({"usds": {"tickers": [{"market": {"identifier": "binance"}}]}})
        cg = CoinGeckoTokens(_Cfg(), http)
        self.assertEqual(cg.exchanges_for("usds"), {"binance"})
        self.assertEqual(cg.exchanges_for(None), set())


if __name__ == "__main__":
    unittest.main()
