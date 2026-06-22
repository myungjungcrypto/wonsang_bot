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
        # CEX 최저가 채택. 반환가는 유효 체결가(테이커 수수료 0.1% 반영).
        venues = {
            "binance": {"price": 1.00, "liq": 5000, "kind": "cex"},
            "gate": {"price": 0.98, "liq": 9000, "kind": "cex"},     # 최저가 → 선택
            "dex:ethereum": {"price": 0.99, "liq": 80000, "kind": "dex"},
        }
        price, venue, _ = choose_buy_venue(venues)
        self.assertEqual(venue, "gate")
        self.assertAlmostEqual(price, 0.98 * 1.001, places=5)

    def test_dex_cheaper_is_jackpot_not_filtered(self):
        # DEX 가 싸고 유동성 크면(슬리피지 작음) 채택(대박). 유효가 = mid×(1+2t/R)×(1+fee).
        venues = {
            "binance": {"price": 1.00, "liq": 5000, "kind": "cex"},
            "dex:bsc": {"price": 0.62, "liq": 500000, "kind": "dex"},
        }
        price, venue, _ = choose_buy_venue(venues)
        self.assertEqual(venue, "dex:bsc")
        self.assertAlmostEqual(price, 0.62 * 1.04 * 1.003, places=5)

    def test_deep_pool_beats_thin_cheaper_pool(self):
        # Phase3 핵심: 얇고 싼 풀(0.50)이 슬리피지로 깊은 풀(0.55)보다 실제 비쌈 → 깊은 풀 채택
        venues = {
            "dex:thin": {"price": 0.50, "liq": 40000, "kind": "dex"},   # 유효 ~0.752
            "dex:deep": {"price": 0.55, "liq": 2_000_000, "kind": "dex"},  # 유효 ~0.557
        }
        price, venue, _ = choose_buy_venue(venues)
        self.assertEqual(venue, "dex:deep")
        self.assertLess(price, 0.60)

    def test_drops_low_liquidity_dex(self):
        # 유동성 부족 DEX($10k 매수 불가)는 제외 → CEX 채택
        venues = {
            "binance": {"price": 1.00, "liq": 5000, "kind": "cex"},
            "dex:ethereum": {"price": 0.05, "liq": 8000, "kind": "dex"},  # reserve<30k → 제외
        }
        price, venue, _ = choose_buy_venue(venues, dex_min_liq=30000)
        self.assertEqual(venue, "binance")
        self.assertAlmostEqual(price, 1.0 * 1.001, places=5)

    def test_dex_only_coin(self):
        # CEX 없고 DEX 풀만 → DEX 채택. 유효가는 슬리피지로 mid 보다 높음.
        venues = {"dex:ethereum": {"price": 0.05, "liq": 50000, "kind": "dex"}}
        price, venue, _ = choose_buy_venue(venues)
        self.assertEqual(venue, "dex:ethereum")
        self.assertGreater(price, 0.05)
        self.assertAlmostEqual(price, 0.05 * 1.4 * 1.003, places=5)

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
