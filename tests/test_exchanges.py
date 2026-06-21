import unittest

from wonsang_bot.collector.exchanges import (
    OverseasAggregator,
    parse_binance,
    parse_bitget,
    parse_bybit,
    parse_gate,
    parse_kucoin,
    parse_okx,
    select_buy_venue,
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


class TestSelectBuyVenue(unittest.TestCase):
    def test_highest_liquidity_among_similar(self):
        venues = {
            "binance": {"price": 1.00, "liq": 5000},
            "gate": {"price": 1.02, "liq": 9000},    # 비슷한 가격 + 최대 유동성 → 선택
            "mexc": {"price": 0.99, "liq": 100},
        }
        price, venue, spread = select_buy_venue(venues)
        self.assertEqual(venue, "gate")
        self.assertAlmostEqual(price, 1.02)

    def test_excludes_price_outlier_collision(self):
        # mexc 가 0.37(다른 토큰, 고유동성)이라도 가격 이상치라 제외, 정상가 채택
        venues = {
            "binance": {"price": 0.17, "liq": 3000},
            "kucoin": {"price": 0.171, "liq": 1000},
            "mexc": {"price": 0.37, "liq": 99999},   # 충돌(가격 이상치) → 제외
        }
        price, venue, spread = select_buy_venue(venues)
        self.assertEqual(venue, "binance")
        self.assertAlmostEqual(price, 0.17)
        self.assertGreater(spread, 1.0)  # 스프레드 큼 → 충돌 신호

    def test_empty(self):
        self.assertEqual(select_buy_venue({}), (None, None, 0.0))


class _FakeEx:
    def __init__(self, name, q):
        self.name = name
        self._q = q

    def quote_at(self, symbol, ts, pad_sec=900):
        return self._q


class TestAggregator(unittest.TestCase):
    def test_aggregates_and_selects(self):
        agg = OverseasAggregator([
            _FakeEx("binance", (1.00, 5000)),
            _FakeEx("gate", (1.01, 8000)),
            _FakeEx("okx", None),
        ])
        q = agg.quote("X", 1000)
        self.assertEqual(q.buy_venue, "gate")
        self.assertEqual(set(q.venues), {"binance", "gate"})

    def test_no_venue(self):
        q = OverseasAggregator([_FakeEx("binance", None)]).quote("X", 1000)
        self.assertIsNone(q.buy_price)


if __name__ == "__main__":
    unittest.main()
