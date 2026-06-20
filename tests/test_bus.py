import asyncio
import unittest

from wonsang_bot.core.bus import EventBus


class Evt:
    def __init__(self, v):
        self.v = v


class OtherEvt:
    pass


class TestBus(unittest.TestCase):
    def test_publish_to_subscribers(self):
        got = []

        async def handler(e):
            got.append(e.v)

        async def run():
            bus = EventBus()
            bus.subscribe(Evt, handler)
            await bus.publish(Evt(1))
            await bus.publish(Evt(2))

        asyncio.run(run())
        self.assertEqual(got, [1, 2])

    def test_only_matching_type(self):
        got = []

        async def handler(e):
            got.append(e.v)

        async def run():
            bus = EventBus()
            bus.subscribe(Evt, handler)
            await bus.publish(OtherEvt())  # 구독 안 한 타입 → 무시

        asyncio.run(run())
        self.assertEqual(got, [])

    def test_handler_error_isolated(self):
        got = []

        async def bad(e):
            raise RuntimeError("boom")

        async def good(e):
            got.append(e.v)

        async def run():
            bus = EventBus()
            bus.subscribe(Evt, bad)
            bus.subscribe(Evt, good)
            await bus.publish(Evt(42))  # bad가 죽어도 good은 실행

        asyncio.run(run())
        self.assertEqual(got, [42])


if __name__ == "__main__":
    unittest.main()
