import unittest

from wonsang_bot.detector.sources.base import html_to_text


class TestHtmlToText(unittest.TestCase):
    def test_strips_tags_and_scripts(self):
        html = "<p>네트워크: 이더리움</p><script>alert('x')</script>"
        self.assertEqual(html_to_text(html), "네트워크: 이더리움")

    def test_unescape_entities(self):
        self.assertIn("A&B", html_to_text("<div>A&amp;B</div>"))

    def test_empty(self):
        self.assertEqual(html_to_text(""), "")
        self.assertEqual(html_to_text(None), "")


if __name__ == "__main__":
    unittest.main()
