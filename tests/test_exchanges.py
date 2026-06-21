import unittest

from wonsang_bot.collector.exchanges import (
    OverseasAggregator,
    Quote,
    parse_bitget,
    parse_bybit,
    parse_gate,
    parse_kucoin,
    parse_okx,
)


class TestParsers(unittest.TestCase):
    def test_bybit(self):
        # result.list: [start_ms, o, h, l, c, vol, turnover]
        p = {"result": {"list": [["1700000000000", "1.0", "1.2", "0.9", "1.15", "5", "5"]]}}
        self.assertEqual(parse_bybit(p), [(1700000000.0, 1.15)])

    def test_okx(self):
        p = {"data": [["1700000000000", "1.0", "1.2", "0.9", "1.3", "5", "5", "5", "1"]]}
        self.assertEqual(parse_okx(p), [(1700000000.0, 1.3)])

    def test_bitget(self):
        p = {"data": [["1700000000000", "1.0", "1.2", "0.9", "1.25", "5", "5"]]}
        self.assertEqual(parse_bitget(p), [(1700000000.0, 1.25)])

    def test_gate(self):
        # [ts_sec, quote_vol, close, high, low, open, ...]
        p = [["1700000000", "1000", "1.4", "1.5", "1.3", "1.35"]]
        self.assertEqual(parse_gate(p), [(1700000000.0, 1.4)])

    def test_kucoin(self):
        # data: [time_sec, open, close, high, low, volume, turnover]
        p = {"data": [["1700000000", "1.0", "1.45", "1.5", "0.9", "5", "5"]]}
        self.assertEqual(parse_kucoin(p), [(1700000000.0, 1.45)])

    def test_garbage_ignored(self):
        self.assertEqual(parse_bybit({}), [])
        self.assertEqual(parse_okx({"data": [["bad"]]}), [])
        self.assertEqual(parse_gate(None), [])


class _FakeEx:
    def __init__(self, name, price):
        self.name = name
        self._price = price

    def price_at(self, symbol, ts, pad_sec=900):
        return self._price


class TestAggregator(unittest.TestCase):
    def test_best_is_min_and_lists_venues(self):
        agg = OverseasAggregator([
            _FakeEx("binance", 1.10),
            _FakeEx("bybit", 1.05),     # 최저
            _FakeEx("okx", None),       # 없음
            _FakeEx("gate", 0),         # 무효(0)
        ])
        q = agg.quote("X", 1000)
        self.assertAlmostEqual(q.best_usd, 1.05)
        self.assertEqual(set(q.venues), {"binance", "bybit"})

    def test_no_venue(self):
        q = OverseasAggregator([_FakeEx("binance", None)]).quote("X", 1000)
        self.assertIsNone(q.best_usd)
        self.assertEqual(q.venues, {})


if __name__ == "__main__":
    unittest.main()
