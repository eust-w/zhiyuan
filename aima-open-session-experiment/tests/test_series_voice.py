import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.synthesize_series_voice import build_voice, load_narration


class SeriesVoiceTests(unittest.TestCase):
    def test_short_narration_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "short.txt"
            path.write_text("太短", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_narration(path)

    def test_build_voice_records_voice_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            narration = Path(tmp) / "stage.txt"
            narration.write_text("这是一个足够长的旁白。" * 100, encoding="utf-8")
            output = Path(tmp) / "stage.mp3"

            async def fake_synthesize(text, output_path, voice, rate):
                output_path.write_bytes(b"voice")

            with patch("scripts.synthesize_series_voice.synthesize", side_effect=fake_synthesize):
                metadata = build_voice(narration, output)

            self.assertEqual(metadata["voice"], "zh-CN-YunyangNeural")
            self.assertEqual(metadata["style"], "沉稳男声")
            self.assertEqual(metadata["narration"], "stage.txt")
            self.assertEqual(metadata["output"], "stage.mp3")
            self.assertTrue(output.with_suffix(".json").exists())


if __name__ == "__main__":
    unittest.main()
