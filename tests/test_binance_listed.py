import unittest

import requests

from wonsang_bot.collector.exchanges import binance_pre_listed
from wonsang_bot.core.events import ListingDetected
from wonsang_bot.predictor.features.base import FeatureContext
from wonsang_bot.predictor.features.binance_listed import BinanceListedFeature


def _ctx(pre):
    return FeatureContext(listing=ListingDetected(
        source="upbit", announcement_id="1", title="t", symbols=["X"],
        is_krw=True, pre_listed_binance=pre,
    ))


class TestBinanceListedFeature(unittest.TestCase):
    def test_on_binance_higher_than_not(self):
        # 데이터상 바이낸스 선상장이 더 좋음(수익↑·안전) → 높은 점수
        on = BinanceListedFeature(1.0).extract(_ctx(True))
        off = BinanceListedFeature(1.0).extract(_ctx(False))
        self.assertTrue(on.available and off.available)
        self.assertGreater(on.score, off.score)

    def test_unknown_unavailable(self):
        self.assertFalse(BinanceListedFeature(1.0).extract(_ctx(None)).available)


class TestBinancePreListed(unittest.TestCase):
    class _Http:
        def __init__(self, rows):
            self._rows = rows

        def get_json(self, url, headers=None):
            if isinstance(self._rows, Exception):
                raise self._rows
            return self._rows

    def test_true_when_candle_exists(self):
        self.assertIs(binance_pre_listed(self._Http([[1, "2"]]), "AAA", 1000), True)

    def test_false_when_empty(self):
        self.assertIs(binance_pre_listed(self._Http([]), "AAA", 1000), False)

    def test_false_on_invalid_symbol_400(self):
        self.assertIs(binance_pre_listed(self._Http(requests.HTTPError("400")), "AAA"),
                      False)

    def test_none_on_network_error(self):
        self.assertIsNone(binance_pre_listed(self._Http(RuntimeError("net")), "AAA"))


if __name__ == "__main__":
    unittest.main()
