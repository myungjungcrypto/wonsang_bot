import hashlib
import json
import os
import tempfile
import unittest

from wonsang_bot.httpclient import HttpClient


class TestHttpCache(unittest.TestCase):
    def test_get_json_cache_hit_skips_network(self):
        d = tempfile.mkdtemp()
        c = HttpClient(cache_dir=d)
        url = "https://example.com/coins/x"
        key = hashlib.sha1(url.encode("utf-8")).hexdigest()
        with open(os.path.join(d, f"{key}.json"), "w", encoding="utf-8") as fh:
            json.dump({"symbol": "x"}, fh)

        def _boom(*a, **k):
            raise AssertionError("네트워크 호출되면 안 됨(캐시 히트)")

        c._send = _boom  # type: ignore[assignment]
        self.assertEqual(c.get_json(url), {"symbol": "x"})

    def test_no_cache_dir_no_files(self):
        c = HttpClient()  # cache_dir 없음 → 캐시 경로 None
        self.assertIsNone(c._cache_path("https://x", "json"))


if __name__ == "__main__":
    unittest.main()
