import tempfile
import unittest
from pathlib import Path

from scripts.build_challenge_video import (
    audio_filter,
    dimensions,
    public_label,
    segment_cache_name,
    should_mask_existing_header,
    source_window,
    transition_duration,
    video_encode_args,
    video_filter,
    video_input_args,
    wrap_subtitle,
    write_srt,
)


class ChallengeVideoRendererTests(unittest.TestCase):
    def test_dimensions_and_public_labels(self):
        self.assertEqual(dimensions(), (1920, 1080))
        self.assertEqual(public_label("real_recording"), "真实录屏")
        self.assertEqual(public_label("real_evidence"), "真实结果")
        self.assertEqual(public_label("metric_animation"), "真实结果")
        self.assertEqual(public_label("diagram"), "流程示意")

    def test_subtitles_wrap_to_sixteen_chinese_characters(self):
        self.assertEqual(
            wrap_subtitle("一二三四五六七八九十", limit=8),
            ["一二三四五六七八", "九十"],
        )
        text = "这是一条需要自动换行而且不能超过十六个汉字的字幕"
        self.assertTrue(all(len(line) <= 16 for line in wrap_subtitle(text)))

    def test_source_window_is_explicit(self):
        self.assertEqual(
            source_window({"source_in_s": 2, "source_out_s": 7}),
            (2.0, 7.0),
        )
        with self.assertRaisesRegex(ValueError, "source window"):
            source_window({"source_in_s": 7, "source_out_s": 2})

    def test_segment_cache_changes_when_source_window_or_overlay_changes(self):
        base = {
            "segment_id": "001-hook",
            "source": "a.mp4",
            "source_in_s": 0,
            "source_out_s": 5,
            "duration_s": 5,
            "overlay": "第一版",
            "subtitle": ["字幕"],
        }
        changed = dict(base, source="b.mp4")
        changed_overlay = dict(base, overlay="第二版")

        self.assertNotEqual(segment_cache_name(base), segment_cache_name(changed))
        self.assertNotEqual(
            segment_cache_name(base),
            segment_cache_name(changed_overlay),
        )

    def test_real_video_input_never_loops_without_permission(self):
        segment = {
            "source_in_s": 2,
            "source_out_s": 7,
            "duration_s": 5,
            "allow_loop": False,
        }

        args = video_input_args(Path("source.mp4"), segment)

        self.assertNotIn("-stream_loop", args)
        self.assertIn("-ss", args)
        self.assertIn("-t", args)

    def test_still_video_filter_has_motion_and_30fps(self):
        filters = video_filter(
            {"duration_s": 4, "source_type": "diagram"},
            is_video=False,
        )

        self.assertIn("zoompan", filters)
        self.assertIn("fps=30", filters)
        self.assertIn("1920", filters)
        self.assertIn("1080", filters)

    def test_real_video_filter_scales_without_destroying_overlays(self):
        filters = video_filter(
            {"duration_s": 8, "source_type": "real_recording"},
            is_video=True,
        )

        self.assertIn("force_original_aspect_ratio=decrease", filters)
        self.assertIn("pad=1920:1080", filters)
        self.assertIn("fps=30", filters)
        self.assertNotIn("crop=", filters)

    def test_old_stage_headers_are_masked_but_canonical_overlays_are_preserved(self):
        self.assertTrue(
            should_mask_existing_header(
                {
                    "source_type": "real_evidence",
                    "source": "assets/screenshots/v3/stage3-paired-metrics.png",
                }
            )
        )
        self.assertTrue(
            should_mask_existing_header(
                {
                    "source_type": "real_recording",
                    "source": "assets/series/recapture/raw/stage2-single-batch-replay.mp4",
                }
            )
        )
        self.assertFalse(
            should_mask_existing_header(
                {
                    "source_type": "real_recording",
                    "source": "assets/series/recapture/canonical/base-eval-2001-annotated.mp4",
                }
            )
        )

    def test_chapter_transition_only_occurs_at_boundary(self):
        self.assertEqual(transition_duration("hook", "hook"), 0)
        self.assertEqual(transition_duration("hook", "baseline"), 0.4)

    def test_audio_filter_ducks_original_bgm_and_normalizes(self):
        filters = audio_filter(duration_s=690, has_music=True)

        self.assertIn("volume=0.28", filters)
        self.assertIn("loudnorm=I=-16:TP=-1.0", filters)
        self.assertIn("apad=whole_dur=690.000", filters)

    def test_encoder_profiles_are_h264(self):
        self.assertIn("h264_videotoolbox", video_encode_args("videotoolbox"))
        self.assertIn("libx264", video_encode_args("libx264"))

    def test_srt_has_at_most_two_short_lines(self):
        manifest = {
            "segments": [
                {
                    "duration_s": 2,
                    "subtitle": ["这是一行很长很长需要换行的中文字幕"],
                },
                {
                    "duration_s": 3,
                    "subtitle": ["第二段字幕"],
                },
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "video.srt"

            write_srt(manifest, output)
            blocks = output.read_text(encoding="utf-8").strip().split("\n\n")

            self.assertEqual(len(blocks), 2)
            for block in blocks:
                lines = block.splitlines()[2:]
                self.assertLessEqual(len(lines), 2)
                self.assertTrue(all(len(line) <= 16 for line in lines))


if __name__ == "__main__":
    unittest.main()
