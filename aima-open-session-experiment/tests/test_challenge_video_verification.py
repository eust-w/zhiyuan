import copy
import tempfile
import unittest
from pathlib import Path

from scripts.build_challenge_video_manifest import build_manifest
from scripts.verify_challenge_video import (
    _stable_ffmpeg_hits,
    acceptance_status,
    subtitle_errors,
    validate_audio_measurement,
    validate_probe,
    validate_storyboard,
)


ROOT = Path(__file__).resolve().parents[1]


class ChallengeVideoVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = build_manifest(ROOT)

    def test_generated_storyboard_passes_all_shallow_checks(self):
        self.assertEqual(validate_storyboard(self.manifest, ROOT), [])

    def test_storyboard_rejects_duration_outside_ten_to_twelve_minutes(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["segments"][-1]["duration_s"] -= 100

        errors = validate_storyboard(manifest, ROOT)

        self.assertTrue(any("duration outside 600-720" in error for error in errors))

    def test_storyboard_rejects_real_ratio_below_eighty_percent(self):
        manifest = copy.deepcopy(self.manifest)
        removed_real = 0.0
        for segment in manifest["segments"]:
            if segment["source_type"] == "real_recording":
                segment["source_type"] = "real_evidence"
                removed_real += segment["duration_s"]
                if removed_real >= 40:
                    break

        errors = validate_storyboard(manifest, ROOT)

        self.assertTrue(any("real recording ratio" in error for error in errors))

    def test_storyboard_rejects_static_segment_longer_than_four_seconds(self):
        manifest = copy.deepcopy(self.manifest)
        static = next(
            item for item in manifest["segments"] if item["source_type"] != "real_recording"
        )
        static["duration_s"] = 4.1

        errors = validate_storyboard(manifest, ROOT)

        self.assertTrue(any("static segment exceeds 4 seconds" in error for error in errors))

    def test_storyboard_rejects_missing_or_duplicate_pair(self):
        manifest = copy.deepcopy(self.manifest)
        paired = [
            item
            for item in manifest["segments"]
            if item.get("pair_episode_id")
        ]
        paired[-1]["pair_episode_id"] = paired[-2]["pair_episode_id"]
        paired[-1]["pair_variant"] = paired[-2]["pair_variant"]

        errors = validate_storyboard(manifest, ROOT)

        self.assertTrue(any("twenty ordered Base/LoRA replays" in error for error in errors))

    def test_storyboard_rejects_metric_drift_and_forbidden_copy(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["facts"]["base"]["success_0_5"] = 10
        manifest["public_framing"] += " 课程"

        errors = validate_storyboard(manifest, ROOT)

        self.assertTrue(any("facts do not match" in error for error in errors))
        self.assertTrue(any("public text" in error for error in errors))

    def test_subtitle_validation_rejects_long_or_three_line_block(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.srt"
            path.write_text(
                "1\n00:00:00,000 --> 00:00:02,000\n"
                "这是超过十六个汉字而且没有正确换行的一整行字幕\n"
                "第二行\n第三行\n",
                encoding="utf-8",
            )

            errors = subtitle_errors(path)

            self.assertTrue(any("more than two lines" in error for error in errors))
            self.assertTrue(any("line exceeds 16" in error for error in errors))

    def test_probe_requires_1080p_h264_and_aac(self):
        good = {
            "format": {"duration": "690.0"},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "30/1",
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "sample_rate": "48000",
                    "channels": 2,
                },
            ],
        }

        self.assertEqual(validate_probe(good), [])
        bad = copy.deepcopy(good)
        bad["streams"][0]["width"] = 1280
        self.assertTrue(validate_probe(bad))

    def test_audio_measurement_requires_target_loudness_and_peak(self):
        self.assertEqual(
            validate_audio_measurement(
                {"integrated_lufs": -16.1, "true_peak_dbfs": -3.9}
            ),
            [],
        )
        self.assertTrue(
            validate_audio_measurement(
                {"integrated_lufs": -20.0, "true_peak_dbfs": -0.2}
            )
        )

    def test_ffmpeg_detector_hits_do_not_retain_process_memory_addresses(self):
        stderr = (
            "[Parsed_freezedetect_0 @ 0x123abc] "
            "lavfi.freezedetect.freeze_duration: 4.1\n"
            "[Parsed_freezedetect_0 @ 0x987def] "
            "lavfi.freezedetect.freeze_duration: 4.5\n"
        )

        self.assertEqual(
            _stable_ffmpeg_hits(stderr, "freeze_duration:"),
            [
                "lavfi.freezedetect.freeze_duration: 4.1",
                "lavfi.freezedetect.freeze_duration: 4.5",
            ],
        )

    def test_acceptance_requires_every_check_to_pass(self):
        self.assertEqual(
            acceptance_status(
                {
                    "storyboard": "passed",
                    "media": "passed",
                    "text": "passed",
                    "audio": "passed",
                }
            ),
            "passed",
        )
        self.assertEqual(
            acceptance_status(
                {
                    "storyboard": "passed",
                    "media": "failed",
                    "text": "passed",
                }
            ),
            "failed",
        )

    def test_real_recording_pauses_are_not_static_storyboard_violations(self):
        real = max(
            (
                item
                for item in self.manifest["segments"]
                if item["source_type"] == "real_recording"
            ),
            key=lambda item: float(item["duration_s"]),
        )
        self.assertGreater(float(real["duration_s"]), 4.0)

        errors = validate_storyboard(self.manifest, ROOT)

        self.assertFalse(
            any(
                error.startswith(f"{real['segment_id']}: static segment exceeds 4 seconds")
                for error in errors
            )
        )


if __name__ == "__main__":
    unittest.main()
