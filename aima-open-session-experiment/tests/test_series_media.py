import unittest


from scripts.build_series_media import real_recording_ratio, wrap_subtitle


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


if __name__ == "__main__":
    unittest.main()
