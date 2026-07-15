import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.verify_series_media import scan_sensitive, subtitle_errors


class SeriesVerificationTests(unittest.TestCase):
    def test_subtitle_lines_are_limited(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.srt"
            path.write_text("1\n00:00:00,000 --> 00:00:01,000\n这是一行明显超过十六个汉字限制的字幕内容\n", encoding="utf-8")
            self.assertTrue(subtitle_errors(path))

    def test_sensitive_scan_finds_email_and_ip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.md").write_text("a@example.com 127.0.0.1", encoding="utf-8")
            self.assertEqual(scan_sensitive(root), ["a.md"])


if __name__ == "__main__":
    unittest.main()
