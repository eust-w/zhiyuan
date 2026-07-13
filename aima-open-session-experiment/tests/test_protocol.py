import json
import tempfile
import unittest
from pathlib import Path

from adapter.protocol import (
    ACTIONS,
    EpisodeReset,
    EpisodeStep,
    ProtocolError,
    build_observation,
    safe_relative_path,
)


class ProtocolTests(unittest.TestCase):
    def test_streamvln_action_contract_is_stable(self):
        self.assertEqual(ACTIONS, {0: "stop", 1: "forward", 2: "left", 3: "right"})
        self.assertEqual(EpisodeStep.from_json({"request_id": "r1", "action_id": 1}).action_id, 1)

    def test_reset_requires_nonempty_episode_instruction_and_target(self):
        reset = EpisodeReset.from_json(
            {
                "schema_version": "geniesim-streamvln/v1",
                "episode_id": "train-0001",
                "seed": 1001,
                "instruction": "Go to the red target marker.",
                "target_id": "red-target",
            }
        )
        self.assertEqual(reset.seed, 1001)
        with self.assertRaises(ProtocolError):
            EpisodeReset.from_json({"episode_id": "", "instruction": "x", "target_id": "y"})

    def test_relative_path_rejects_escape_and_absolute_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = root / "runs" / "e1" / "rgb" / "000.jpg"
            good.parent.mkdir(parents=True)
            good.write_bytes(b"x")
            self.assertEqual(safe_relative_path(root, good), "runs/e1/rgb/000.jpg")
            with self.assertRaises(ProtocolError):
                safe_relative_path(root, root.parent / "secret.txt")
            with self.assertRaises(ProtocolError):
                safe_relative_path(root, Path("/etc/passwd"))

    def test_observation_is_json_serializable_and_contains_required_fields(self):
        obs = build_observation(
            episode_id="e1",
            step_id=2,
            rgb_path="runs/e1/rgb/002.jpg",
            depth_path="runs/e1/depth/002.png",
            pose_matrix=[1.0] * 16,
            distance_to_goal_m=0.4,
            collision=False,
            blocked=False,
            terminated=True,
            truncated=False,
        )
        payload = json.loads(json.dumps(obs))
        self.assertEqual(payload["episode_id"], "e1")
        self.assertIn("distance_to_goal_m", payload)
        self.assertEqual(len(payload["pose_matrix"]), 16)


if __name__ == "__main__":
    unittest.main()

