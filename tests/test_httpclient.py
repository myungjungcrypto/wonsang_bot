import unittest

from wonsang_bot.httpclient import HttpClient


class _Resp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self.headers = {}
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class TestRetry(unittest.TestCase):
    def test_retries_on_429_then_succeeds(self):
        c = HttpClient(min_interval=0, max_retries=3, backoff=0.0)
        n = {"c": 0}

        def fake(method, url, **kw):
            n["c"] += 1
            return _Resp(429 if n["c"] < 3 else 200, {"ok": True})

        c._session.request = fake
        self.assertEqual(c.get_json("http://x"), {"ok": True})
        self.assertEqual(n["c"], 3)  # 2번 429 후 3번째 성공

    def test_gives_up_after_max_retries(self):
        c = HttpClient(min_interval=0, max_retries=2, backoff=0.0)
        n = {"c": 0}

        def fake(method, url, **kw):
            n["c"] += 1
            return _Resp(429)

        c._session.request = fake
        with self.assertRaises(RuntimeError):
            c.get_json("http://x")
        self.assertEqual(n["c"], 3)  # 최초 1 + 재시도 2

    def test_no_retry_on_400(self):
        c = HttpClient(min_interval=0, max_retries=3, backoff=0.0)
        n = {"c": 0}

        def fake(method, url, **kw):
            n["c"] += 1
            return _Resp(400)

        c._session.request = fake
        with self.assertRaises(RuntimeError):
            c.get_json("http://x")
        self.assertEqual(n["c"], 1)  # 400은 재시도 안 함


if __name__ == "__main__":
    unittest.main()
