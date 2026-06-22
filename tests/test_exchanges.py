import unittest

from wonsang_bot.collector.exchanges import (
    OverseasAggregator,
    choose_buy_venue,
    parse_binance,
    parse_bitget,
    parse_bybit,
    parse_gate,
    parse_kucoin,
    parse_okx,
)


class TestParsers(unittest.TestCase):
    def test_binance_triple(self):
        # [openMs,o,h,l,c,baseVol,closeMs,quoteVol,...]
        p = [[1700000000000, "1", "1.2", "0.9", "1.1", "100", 1700000059999, "111.0"]]
        self.assertEqual(parse_binance(p), [(1700000000.0, 1.1, 111.0)])

    def test_bybit(self):
        p = {"result": {"list": [["1700000000000", "1", "1.2", "0.9", "1.15", "5", "777"]]}}
        self.assertEqual(parse_bybit(p), [(1700000000.0, 1.15, 777.0)])

    def test_okx(self):
        p = {"data": [["1700000000000", "1", "1.2", "0.9", "1.3", "5", "6", "888", "1"]]}
        self.assertEqual(parse_okx(p), [(1700000000.0, 1.3, 888.0)])

    def test_gate(self):
        # [ts, quoteVol, close, high, low, open, ...]
        p = [["1700000000", "999", "1.4", "1.5", "1.3", "1.35"]]
        self.assertEqual(parse_gate(p), [(1700000000.0, 1.4, 999.0)])

    def test_kucoin(self):
        p = {"data": [["1700000000", "1", "1.45", "1.5", "0.9", "5", "555"]]}
        self.assertEqual(parse_kucoin(p), [(1700000000.0, 1.45, 555.0)])

    def test_bitget(self):
        p = {"data": [["1700000000000", "1", "1.2", "0.9", "1.25", "5", "444"]]}
        self.assertEqual(parse_bitget(p), [(1700000000.0, 1.25, 444.0)])


class TestChooseBuyVenue(unittest.TestCase):
    def test_cheapest_among_liquidity_survivors(self):
        # 같은 토큰(신원확정)이면 더 싼 곳이 더 좋은 매수처 → 최저가 채택
        venues = {
            "binance": {"price": 1.00, "liq": 5000, "kind": "cex"},
            "gate": {"price": 0.98, "liq": 9000, "kind": "cex"},     # 최저가 → 선택
            "dex:ethereum": {"price": 0.99, "liq": 80000, "kind": "dex"},
        }
        price, venue, _ = choose_buy_venue(venues)
        self.assertEqual(venue, "gate")
        self.assertAlmostEqual(price, 0.98)

    def test_dex_cheaper_is_jackpot_not_filtered(self):
        # DEX 가 CEX 보다 싸도(컨트랙트로 같은 토큰 확정) 걸러지지 않고 채택(대박)
        venues = {
            "binance": {"price": 1.00, "liq": 5000, "kind": "cex"},
            "dex:bsc": {"price": 0.62, "liq": 500000, "kind": "dex"},  # 싸고 유동성 큼
        }
        price, venue, _ = choose_buy_venue(venues)
        self.assertEqual(venue, "dex:bsc")
        self.assertAlmostEqual(price, 0.62)

    def test_drops_low_liquidity_dex(self):
        # 유동성 부족 DEX($10k 매수 불가)는 가격 무관 제외 → CEX 채택
        venues = {
            "binance": {"price": 1.00, "liq": 5000, "kind": "cex"},
            "dex:ethereum": {"price": 0.05, "liq": 8000, "kind": "dex"},  # reserve<30k → 제외
        }
        price, venue, _ = choose_buy_venue(venues, dex_min_liq=30000)
        self.assertEqual(venue, "binance")
        self.assertAlmostEqual(price, 1.0)

    def test_dex_only_coin(self):
        # CEX 어디에도 없고 DEX 풀만(유동성 충분) → DEX 채택
        venues = {"dex:ethereum": {"price": 0.05, "liq": 50000, "kind": "dex"}}
        price, venue, _ = choose_buy_venue(venues)
        self.assertEqual(venue, "dex:ethereum")
        self.assertAlmostEqual(price, 0.05)

    def test_empty(self):
        self.assertEqual(choose_buy_venue({}), (None, None, 0.0))


class _FakeEx:
    def __init__(self, name, q):
        self.name = name
        self._q = q

    def quote_at(self, symbol, ts, pad_sec=900):
        return self._q


class TestAggregator(unittest.TestCase):
    def test_aggregates_and_picks_cheapest(self):
        agg = OverseasAggregator([
            _FakeEx("binance", (0.99, 5000)),   # 최저가 → 선택
            _FakeEx("gate", (1.01, 8000)),
            _FakeEx("okx", None),
        ])
        q = agg.quote("X", 1000)
        self.assertEqual(q.buy_venue, "binance")
        self.assertEqual(set(q.venues), {"binance", "gate"})

    def test_only_restricts_exchanges(self):
        # only 집합 밖 거래소는 조회 자체를 건너뜀(신원검증된 곳만)
        agg = OverseasAggregator([
            _FakeEx("binance", (1.00, 5000)),
            _FakeEx("mexc", (0.37, 99999)),    # 충돌 토큰이지만 only 에 없어 제외
        ])
        venues = agg.fetch_venues("X", 1000, only={"binance"})
        self.assertEqual(set(venues), {"binance"})

    def test_no_venue(self):
        q = OverseasAggregator([_FakeEx("binance", None)]).quote("X", 1000)
        self.assertIsNone(q.buy_price)


if __name__ == "__main__":
    unittest.main()
