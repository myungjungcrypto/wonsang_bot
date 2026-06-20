import unittest

from wonsang_bot.core.events import Announcement
from wonsang_bot.detector.diff import find_new


def _ann(source, id_, title="t"):
    return Announcement(source=source, id=id_, title=title)


class TestDiff(unittest.TestCase):
    def test_all_new_when_empty_seen(self):
        fetched = [_ann("upbit", "1"), _ann("upbit", "2")]
        self.assertEqual(len(find_new(fetched, set())), 2)

    def test_filters_seen(self):
        fetched = [_ann("upbit", "1"), _ann("upbit", "2"), _ann("upbit", "3")]
        seen = {"upbit:1", "upbit:3"}
        new = find_new(fetched, seen)
        self.assertEqual([a.id for a in new], ["2"])

    def test_source_namespacing(self):
        # 같은 id라도 source가 다르면 별개
        fetched = [_ann("bithumb", "1")]
        seen = {"upbit:1"}
        self.assertEqual(len(find_new(fetched, seen)), 1)

    def test_preserves_order(self):
        fetched = [_ann("upbit", "5"), _ann("upbit", "4"), _ann("upbit", "6")]
        new = find_new(fetched, set())
        self.assertEqual([a.id for a in new], ["5", "4", "6"])


if __name__ == "__main__":
    unittest.main()
