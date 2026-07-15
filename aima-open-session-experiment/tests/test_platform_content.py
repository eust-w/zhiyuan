import json
import unittest
from pathlib import Path

from scripts.build_platform_copy import build_package
from scripts.verify_series_content import build_report


ROOT = Path(__file__).resolve().parents[1]


class PlatformContentTests(unittest.TestCase):
    def test_inventory_has_four_stages_and_required_evidence(self):
        inventory = json.loads((ROOT / "content/series/platform-content.json").read_text(encoding="utf-8"))
        self.assertEqual({item["episode"] for item in inventory["episodes"]}, {"stage0", "stage1", "stage2", "stage3"})
        self.assertEqual(inventory["primary_metric"], "success@0.5m")
        self.assertTrue(all(len(item["evidence_images"]) >= 10 for item in inventory["episodes"]))

    def test_package_builds_platform_specific_files(self):
        with __import__("tempfile").TemporaryDirectory() as tmp:
            output = Path(tmp)
            generated = build_package(ROOT, ROOT / "content/series/platform-content.json", output)
            self.assertEqual(len(generated), 17)
            self.assertTrue((output / "bilibili-stage3.md").exists())
            zhihu = (output / "zhihu-stage3.md").read_text(encoding="utf-8")
            self.assertIn("success@0.5m", zhihu)
            self.assertGreaterEqual(len(zhihu), 3000)
            self.assertLessEqual(len(zhihu), 5000)
            self.assertIn("置顶评论", (output / "douyin-stage0.md").read_text(encoding="utf-8"))

    def test_checked_in_platform_package_passes_length_and_wording_gates(self):
        report = build_report(ROOT)
        self.assertEqual(report["status"], "passed", report["errors"])


if __name__ == "__main__":
    unittest.main()
