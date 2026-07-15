import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.build_original_bgm import build_bgm


class OriginalBgmTests(unittest.TestCase):
    def test_build_bgm_records_provenance_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "ambient.wav"

            def fake_ffmpeg(command, check):
                output.write_bytes(b"synthetic-audio")

            with patch("scripts.build_original_bgm.subprocess.run", side_effect=fake_ffmpeg):
                metadata = build_bgm(output, 12.0)

            self.assertEqual(metadata["license"], "original local synthesis; no third-party recording")
            self.assertEqual(len(metadata["sha256"]), 64)
            self.assertTrue(output.with_suffix(".json").exists())


if __name__ == "__main__":
    unittest.main()
