import unittest
from collections import namedtuple

from wonsang_bot.collector.buyrouting import gather_buy_route, make_venue_provider
from wonsang_bot.collector.coingecko import ResolvedToken
from wonsang_bot.config import Config
from wonsang_bot.core.events import Contract, ListingDetected
from wonsang_bot.predictor.features import build_extractors
from wonsang_bot.predictor.service import PredictorService

C = namedtuple("C", "chain address")


class _Overseas:
    def __init__(self, venues):
        self._v = venues

    def fetch_venues(self, symbol, ts, only=None):
        if only is None:
            return dict(self._v)
        return {k: v for k, v in self._v.items() if k in only}


class _Dex:
    def __init__(self, by_chain):
        self._b = by_chain  # {chain: (price, liq) | None}

    def quote_at(self, chain, address, ts):
        return self._b.get(chain)


class _CG:
    def __init__(self, by_addr):
        self._r = by_addr

    def resolve(self, chain, address):
        return self._r.get(address, ResolvedToken(None, {chain: address}))


class _Bus:
    def subscribe(self, *a):
        pass


class TestGatherBuyRoute(unittest.TestCase):
    def test_cheapest_across_cex_and_dex_chains(self):
        cg = _CG({"0xIRYS": ResolvedToken("irys", {"ethereum": "0xIRYS", "bsc": "0xBSC"},
                                          "irys", {"binance"})})
        overseas = _Overseas({"binance": {"price": 0.10, "liq": 5000, "kind": "cex"}})
        dex = _Dex({"ethereum": (0.09, 8000),      # 유동성<30k → 선택 제외
                    "bsc": (0.062, 500000)})        # 진짜 유동성 → 최저가
        r = gather_buy_route("IRYS", 1000, [C("ethereum", "0xIRYS")],
                             overseas=overseas, dex=dex, cg_tokens=cg)
        self.assertEqual(r.buy_venue, "dex:bsc")
        self.assertAlmostEqual(r.buy_price, 0.062)
        self.assertTrue(r.used_dex)
        self.assertEqual(r.coin_id, "irys")
        self.assertEqual(r.venue_count, 3)  # binance + dex:ethereum + dex:bsc

    def test_mismatch_contract_different_token(self):
        # 공지 컨트랙트가 SKY 인데 상장은 USDS → 다른 토큰 → mismatch
        cg = _CG({"0xSKY": ResolvedToken("sky", {"ethereum": "0xSKY"}, "sky", set())})
        r = gather_buy_route("USDS", 1000, [C("ethereum", "0xSKY")],
                             overseas=_Overseas({}), dex=_Dex({}), cg_tokens=cg)
        self.assertTrue(r.mismatch)
        self.assertIsNone(r.buy_price)

    def test_provider_returns_venue_dict(self):
        cg = _CG({"0xX": ResolvedToken("x", {"ethereum": "0xX"}, "x", {"binance"})})
        overseas = _Overseas({"binance": {"price": 1.0, "liq": 9, "kind": "cex"}})
        provider = make_venue_provider(overseas, _Dex({}), cg)
        listing = ListingDetected(source="upbit", announcement_id="1", title="t",
                                  symbols=["X"], is_krw=True,
                                  contracts=[Contract(chain="ethereum", address="0xX")])
        out = provider(listing)
        self.assertEqual(out["venue_count"], 1)
        self.assertEqual(out["buy_venue"], "binance")


class TestPredictWithVenue(unittest.TestCase):
    def test_venue_count_active_and_buy_on_grade(self):
        svc = PredictorService(
            Config(), None, _Bus(), build_extractors(Config()),
            venue_provider=lambda ev: {"venue_count": 5, "buy_venue": "binance",
                                       "buy_price": 0.1234},
        )
        ev = ListingDetected(source="upbit", announcement_id="1", title="t",
                             symbols=["X"], is_krw=True)
        pred = svc.predict(ev)
        self.assertEqual(pred.venue_count, 5)
        self.assertEqual(pred.buy_venue, "binance")
        vc = next(f for f in pred.features if f.name == "venue_count")
        self.assertTrue(vc.available)
        self.assertGreater(vc.score, 0.8)  # 5곳 → 높은 점수


if __name__ == "__main__":
    unittest.main()
