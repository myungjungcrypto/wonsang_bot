import unittest
from collections import namedtuple

from wonsang_bot.collector.buyrouting import BuyRoute, find_bridge_route
from wonsang_bot.collector.lifi import LiFiClient, parse_route


class _Cfg:
    lifi_base_url = "https://li.quest/v1"
    lifi_api_key = None


class _Http:
    def __init__(self, payload):
        self.payload = payload
        self.last_url = None

    def get_json(self, url, headers=None):
        self.last_url = url
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


_QUOTE = {
    "tool": "stargate",
    "toolDetails": {"key": "stargate", "name": "Stargate"},
    "estimate": {"fromAmount": "1000000000000000000", "toAmount": "995000000000000000",
                 "executionDuration": 120},
}


class TestParseRoute(unittest.TestCase):
    def test_parses_tool_amount_duration(self):
        r = parse_route(_QUOTE)
        self.assertEqual(r["tool"], "Stargate")
        self.assertEqual(r["to_amount"], "995000000000000000")
        self.assertEqual(r["duration_sec"], 120)

    def test_none_on_empty(self):
        self.assertIsNone(parse_route({}))
        self.assertIsNone(parse_route(None))


class TestLiFiClient(unittest.TestCase):
    def test_route_builds_params_and_parses(self):
        http = _Http(_QUOTE)
        c = LiFiClient(_Cfg(), http)
        r = c.route("bsc", "0xFROM", "ethereum", "0xTO", "1000000000000000000")
        self.assertEqual(r["tool"], "Stargate")
        self.assertEqual(r["from_chain"], "bsc")
        self.assertEqual(r["to_chain"], "ethereum")
        self.assertIn("fromChain=bsc", http.last_url)
        self.assertIn("toChain=eth", http.last_url)

    def test_unknown_chain_none(self):
        c = LiFiClient(_Cfg(), _Http(_QUOTE))
        self.assertIsNone(c.route("unknownchain", "0xF", "ethereum", "0xT", "1"))


C = namedtuple("C", "chain address")


class _LiFi:
    def __init__(self, out):
        self.out = out
        self.called = False

    def route(self, fc, ft, tc, tt, amt, addr=None):
        self.called = True
        return dict(self.out, from_chain=fc, to_chain=tc)


class TestFindBridgeRoute(unittest.TestCase):
    def _route(self, venue, platforms):
        return BuyRoute(buy_price=0.06, buy_venue=venue, platforms=platforms)

    def test_bridge_when_buy_chain_differs(self):
        r = self._route("dex:bsc", {"bsc": "0xBSC", "ethereum": "0xETH"})
        lifi = _LiFi({"tool": "Stargate"})
        out = find_bridge_route(r, "ethereum", lifi)
        self.assertTrue(lifi.called)
        self.assertEqual(out["tool"], "Stargate")
        self.assertEqual(out["from_chain"], "bsc")

    def test_no_bridge_same_chain(self):
        r = self._route("dex:ethereum", {"ethereum": "0xETH"})
        lifi = _LiFi({"tool": "X"})
        self.assertIsNone(find_bridge_route(r, "ethereum", lifi))
        self.assertFalse(lifi.called)

    def test_no_bridge_for_cex(self):
        # CEX 매수는 출금 시 네트워크 선택 → 브릿지 불필요
        r = self._route("okx", {"ethereum": "0xETH", "bsc": "0xBSC"})
        lifi = _LiFi({"tool": "X"})
        self.assertIsNone(find_bridge_route(r, "ethereum", lifi))

    def test_no_lifi_or_network(self):
        r = self._route("dex:bsc", {"bsc": "0xB", "ethereum": "0xE"})
        self.assertIsNone(find_bridge_route(r, "ethereum", None))
        self.assertIsNone(find_bridge_route(r, None, _LiFi({"tool": "X"})))


if __name__ == "__main__":
    unittest.main()
