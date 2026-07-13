import json
import tempfile
import unittest
from pathlib import Path

from adapter.dataset import DatasetError, build_annotation, validate_dataset


class DatasetTests(unittest.TestCase):
    def test_annotation_preserves_initial_placeholder_and_omits_stop(self):
        row = build_annotation(
            episode_id="train-0001",
            instruction="Go to the red target marker.",
            rgb_dir="images/train-0001",
            non_stop_actions=[1, 2, 1],
        )
        self.assertEqual(row["actions"], [-1, 1, 2, 1])
        self.assertEqual(row["video"], "images/train-0001")

    def test_validator_checks_frame_action_alignment_and_initial_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_dir = root / "images" / "e1" / "rgb"
            image_dir.mkdir(parents=True)
            for name in ("000.jpg", "001.jpg", "002.jpg", "003.jpg"):
                (image_dir / name).write_bytes(b"not-an-image")
            (root / "annotations.json").write_text(
                json.dumps([{"id": "e1", "video": "images/e1", "instructions": ["x"], "actions": [-1, 1, 2, 1]}]),
                encoding="utf-8",
            )
            report = validate_dataset(root, verify_image_bytes=False)
            self.assertEqual(report["episodes"], 1)
            self.assertEqual(report["valid"], 1)

    def test_validator_rejects_final_stop_in_public_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "images" / "e1" / "rgb").mkdir(parents=True)
            for name in ("000.jpg", "001.jpg"):
                (root / "images" / "e1" / "rgb" / name).write_bytes(b"x")
            (root / "annotations.json").write_text(
                json.dumps([{"id": "e1", "video": "images/e1", "instructions": ["x"], "actions": [-1, 1, 0]}]),
                encoding="utf-8",
            )
            with self.assertRaises(DatasetError):
                validate_dataset(root, verify_image_bytes=False)


if __name__ == "__main__":
    unittest.main()

