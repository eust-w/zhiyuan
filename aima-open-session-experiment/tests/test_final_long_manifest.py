import unittest
from pathlib import Path

from scripts.build_final_long_manifest import build_manifest


ROOT = Path(__file__).resolve().parents[1]


class FinalLongManifestTests(unittest.TestCase):
    def test_each_episode_is_ten_minutes_with_at_least_seventy_five_percent_real_recording(self):
        manifest = build_manifest(ROOT)

        for episode in manifest["episodes"]:
            total = sum(segment["duration_s"] for segment in episode["segments"])
            real = sum(
                segment["duration_s"]
                for segment in episode["segments"]
                if segment["source_type"] == "real_recording"
            )
            self.assertEqual(total, 600)
            self.assertGreaterEqual(real / total, 0.75)

    def test_static_segments_never_exceed_six_seconds(self):
        manifest = build_manifest(ROOT)

        for episode in manifest["episodes"]:
            for segment in episode["segments"]:
                if segment["source_type"] != "real_recording":
                    self.assertLessEqual(segment["duration_s"], 6)

    def test_stage3_uses_all_twenty_distinct_canonical_paired_replays(self):
        manifest = build_manifest(ROOT)
        stage3 = next(item for item in manifest["episodes"] if item["episode"] == "stage3")
        canonical = [
            segment["source"]
            for segment in stage3["segments"]
            if "/recapture/canonical/" in segment["source"]
        ]

        self.assertEqual(len(canonical), 20)
        self.assertEqual(len(set(canonical)), 20)


if __name__ == "__main__":
    unittest.main()
