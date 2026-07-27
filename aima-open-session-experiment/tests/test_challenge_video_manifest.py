import unittest
from collections import Counter, defaultdict
from pathlib import Path

from scripts.build_challenge_video_manifest import (
    CHAPTER_TARGETS,
    REQUIRED_SEGMENT_FIELDS,
    build_manifest,
    narration_character_count,
    probe_duration,
)
from scripts.challenge_video_contract import (
    APPROVED_CERTIFICATE_COPY,
    scan_public_bundle,
)


ROOT = Path(__file__).resolve().parents[1]


class ChallengeVideoManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = build_manifest(ROOT)

    def test_duration_ratio_chapters_and_static_limits(self):
        manifest = self.manifest
        segments = manifest["segments"]
        total = sum(item["duration_s"] for item in segments)
        real = sum(
            item["duration_s"]
            for item in segments
            if item["source_type"] == "real_recording"
        )

        self.assertGreaterEqual(total, 600)
        self.assertLessEqual(total, 720)
        self.assertGreaterEqual(real / total, 0.80)
        self.assertEqual(
            manifest["chapter_ids"],
            [
                "hook",
                "baseline",
                "operation",
                "data",
                "training",
                "paired_eval",
                "innovation",
                "closing",
            ],
        )
        self.assertTrue(
            all(
                item["duration_s"] <= 4
                for item in segments
                if item["source_type"] != "real_recording"
            )
        )

    def test_chapter_totals_match_approved_schedule(self):
        totals = defaultdict(float)
        for segment in self.manifest["segments"]:
            totals[segment["chapter_id"]] += segment["duration_s"]

        self.assertEqual(dict(totals), CHAPTER_TARGETS)

    def test_every_segment_has_complete_safe_metadata(self):
        for segment in self.manifest["segments"]:
            with self.subTest(segment=segment["segment_id"]):
                self.assertTrue(REQUIRED_SEGMENT_FIELDS.issubset(segment))
                self.assertIn(
                    segment["public_label"],
                    {"真实录屏", "真实结果", "流程示意"},
                )
                self.assertFalse(Path(segment["source"]).is_absolute())
                self.assertFalse(Path(segment["evidence_ref"]).is_absolute())
                self.assertTrue((ROOT / segment["source"]).is_file())
                self.assertTrue((ROOT / segment["evidence_ref"]).is_file())

    def test_real_source_windows_fit_without_looping(self):
        windows = defaultdict(list)
        for segment in self.manifest["segments"]:
            if segment["source_type"] != "real_recording":
                continue
            source = ROOT / segment["source"]
            duration = probe_duration(source)
            self.assertGreaterEqual(segment["source_in_s"], 0)
            self.assertLessEqual(segment["source_out_s"], duration + 0.02)
            self.assertAlmostEqual(
                segment["source_out_s"] - segment["source_in_s"],
                segment["duration_s"],
                places=3,
            )
            self.assertFalse(segment.get("allow_loop", False))
            windows[segment["source"]].append(
                (segment["source_in_s"], segment["source_out_s"])
            )
        for source, items in windows.items():
            ordered = sorted(items)
            for previous, current in zip(ordered, ordered[1:]):
                with self.subTest(source=source):
                    self.assertLessEqual(previous[1], current[0] + 0.001)

    def test_real_recording_segments_do_not_flash_for_less_than_two_seconds(self):
        for segment in self.manifest["segments"]:
            if segment["source_type"] == "real_recording":
                with self.subTest(segment=segment["segment_id"]):
                    self.assertGreaterEqual(segment["duration_s"], 2)

    def test_stage3_uses_all_twenty_distinct_paired_replays(self):
        manifest = self.manifest
        expected_ids = [f"eval-{seed}" for seed in range(2001, 2011)]

        self.assertEqual(manifest["paired_episode_ids"], expected_ids)
        self.assertEqual(len(manifest["paired_replays"]), 20)
        self.assertEqual(len(set(manifest["paired_replays"])), 20)
        pairs = Counter(
            (item["pair_episode_id"], item["pair_variant"])
            for item in manifest["segments"]
            if item["chapter_id"] == "paired_eval"
            and item["source_type"] == "real_recording"
        )
        self.assertEqual(
            pairs,
            Counter(
                (episode_id, variant)
                for episode_id in expected_ids
                for variant in ("base", "lora")
            ),
        )

    def test_narration_is_long_complete_and_public_safe(self):
        sections = self.manifest["narration_sections"]
        count = narration_character_count(sections)

        self.assertGreaterEqual(count, 2200)
        self.assertLessEqual(count, 2700)
        self.assertTrue(sections[0]["text"].startswith("画面里的机器人"))
        self.assertIn(APPROVED_CERTIFICATE_COPY, sections[-2]["text"])
        self.assertTrue(
            sections[-1]["text"].endswith(
                "真正的挑战，不是做出一段演示，而是让每一个结果都经得起复核。"
            )
        )
        self.assertEqual(scan_public_bundle(self.manifest), [])

    def test_fact_snapshot_is_embedded_without_handwritten_metric_drift(self):
        facts = self.manifest["facts"]

        self.assertEqual(facts["base"]["success_0_5"], 0)
        self.assertEqual(facts["lora"]["success_0_5"], 0)
        self.assertEqual(facts["base"]["success_3"], 2)
        self.assertEqual(facts["lora"]["success_3"], 1)
        self.assertEqual(facts["base"]["collisions"], 132)
        self.assertEqual(facts["lora"]["collisions"], 45)
        self.assertEqual(
            facts["lora"]["mean_final_distance_to_goal"],
            4.686244300975281,
        )


if __name__ == "__main__":
    unittest.main()
