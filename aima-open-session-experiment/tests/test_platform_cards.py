import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.build_platform_cards import build


ROOT = Path(__file__).resolve().parents[1]


class PlatformCardTests(unittest.TestCase):
    def test_builder_renders_expected_card_counts_and_dimensions(self):
        expected = {"stage0": 8, "stage1": 9, "stage2": 9, "stage3": 10}
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            manifests = build(ROOT / "content/series/platform-content.json", output)
            self.assertEqual(len(manifests), 4)
            for stage, count in expected.items():
                manifest = json.loads((output / stage / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["count"], count)
                self.assertEqual(len(manifest["cards"]), count)
                self.assertTrue(all(card["label"] in {"真实录屏帧", "真实结果图", "真实指标图", "AI 示意图"} for card in manifest["cards"]))
                with Image.open(output / stage / "card-01.png") as image:
                    self.assertEqual(image.size, (1080, 1440))


if __name__ == "__main__":
    unittest.main()
