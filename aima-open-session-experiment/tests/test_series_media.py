import unittest
import tempfile


from pathlib import Path

from PIL import Image

from scripts.build_series_media import overlay_image, public_path, real_recording_ratio, wrap_subtitle


class SeriesMediaTests(unittest.TestCase):
    def test_real_recording_ratio_uses_segment_durations(self):
        episode = {
            "segments": [
                {"duration_s": 8, "source_type": "real_recording"},
                {"duration_s": 1, "source_type": "real_evidence"},
                {"duration_s": 1, "source_type": "metric_animation"},
            ]
        }
        self.assertAlmostEqual(real_recording_ratio(episode), 0.8)

    def test_wrap_subtitle_keeps_each_line_at_or_below_sixteen_characters(self):
        lines = wrap_subtitle("这是一个用于验证字幕自动换行的中文长句子", 16)
        self.assertGreater(len(lines), 1)
        self.assertTrue(all(len(line) <= 16 for line in lines))

    def test_wrap_subtitle_does_not_leave_boundary_whitespace(self):
        lines = wrap_subtitle("59 步更新：0.4167 → 0.0823", 16)

        self.assertTrue(all(line == line.strip() for line in lines))

    def test_public_path_does_not_expose_the_local_workspace_prefix(self):
        root = Path("/private/workspace/project")

        value = public_path(root / "assets/series/stage2/stage2.mp4", root)

        self.assertEqual(value, "assets/series/stage2/stage2.mp4")

    def test_overlay_preserves_an_annotated_source_dashboard(self):
        episode = {"episode": "stage3"}
        segment = {
            "segment_id": "stage3-02",
            "source_type": "real_recording",
            "overlay": "unused",
            "narration": "unused",
            "preserve_source_overlay": True,
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "overlay.png"
            overlay_image(episode, segment, path)
            image = Image.open(path)

        self.assertEqual(image.getpixel((960, 1000))[3], 0)
        self.assertEqual(image.getpixel((100, 80))[3], 0)


if __name__ == "__main__":
    unittest.main()
