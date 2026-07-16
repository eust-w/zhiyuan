import unittest
from pathlib import Path

from scripts.build_final_long_manifest import build_manifest
from scripts.verify_final_long import acceptance_status, validate_storyboard


ROOT = Path(__file__).resolve().parents[1]


class FinalLongVerificationTests(unittest.TestCase):
    def test_generated_storyboard_passes_duration_ratio_and_static_checks(self):
        errors = validate_storyboard(build_manifest(ROOT))

        self.assertEqual(errors, [])

    def test_storyboard_rejects_a_static_segment_longer_than_six_seconds(self):
        manifest = build_manifest(ROOT)
        manifest["episodes"][0]["segments"][1]["duration_s"] = 7

        errors = validate_storyboard(manifest)

        self.assertTrue(any("static segment" in error for error in errors))

    def test_acceptance_requires_every_media_check_and_no_sensitive_hits(self):
        self.assertEqual(acceptance_status([{"status": "passed"}] * 4, []), "passed")
        self.assertEqual(acceptance_status([{"status": "failed"}], []), "failed")
        self.assertEqual(acceptance_status([{"status": "passed"}] * 4, ["secret.srt"]), "failed")


if __name__ == "__main__":
    unittest.main()
