import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.verify_series_media import acceptance_status, public_media_path, scan_sensitive, subtitle_errors


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

    def test_sensitive_scan_finds_local_and_remote_absolute_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.json").write_text(
                '{"local": "/Users/example/work/project", "remote": "/root/private/model"}',
                encoding="utf-8",
            )

            self.assertEqual(scan_sensitive(root), ["a.json"])

    def test_sensitive_scan_skips_explicitly_private_raw_recapture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "recapture" / "raw"
            raw.mkdir(parents=True)
            (raw / "private.json").write_text('{"host": "127.0.0.1"}', encoding="utf-8")
            (root / "public.json").write_text('{"status": "passed"}', encoding="utf-8")

            self.assertEqual(scan_sensitive(root), [])

    def test_acceptance_is_blocked_by_a_public_sensitive_hit(self):
        outputs = [{"status": "passed"}]

        self.assertEqual(acceptance_status(outputs, [], ["public.json"]), "draft_blocked")

    def test_public_media_path_is_repository_relative(self):
        root = Path("/private/workspace/project")

        self.assertEqual(public_media_path(root / "assets/series/stage3/stage3.mp4", root), "assets/series/stage3/stage3.mp4")


if __name__ == "__main__":
    unittest.main()
