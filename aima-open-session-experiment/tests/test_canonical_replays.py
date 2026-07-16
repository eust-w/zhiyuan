import unittest

import numpy as np

from scripts.build_canonical_replays import (
    ACTION_LABELS,
    expanded_actions,
    render_dashboard,
)


class CanonicalReplayTests(unittest.TestCase):
    def test_expanded_actions_aligns_transitions_with_observation_frames(self):
        predictions = [
            {"step_id": 0, "actions": [2, 1, 2]},
            {"step_id": 3, "actions": [3, 0]},
        ]

        self.assertEqual(expanded_actions(predictions, observation_count=6), [-1, 2, 1, 2, 3, 0])

    def test_expanded_actions_pads_missing_transitions_as_unknown(self):
        predictions = [{"step_id": 0, "actions": [1]}]

        self.assertEqual(expanded_actions(predictions, observation_count=4), [-1, 1, -1, -1])

    def test_render_dashboard_adds_chinese_metrics_and_trajectory_panel(self):
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        observations = [
            {
                "step_id": 0,
                "distance_to_goal_m": 4.0,
                "blocked": False,
                "collision": False,
                "pose_matrix": [1, 0, 0, 0.0, 0, 1, 0, 0.0, 0, 0, 1, 0, 0, 0, 0, 1],
                "target_xy": [2.0, 1.0],
            },
            {
                "step_id": 1,
                "distance_to_goal_m": 3.75,
                "blocked": True,
                "collision": True,
                "pose_matrix": [1, 0, 0, 0.25, 0, 1, 0, 0.0, 0, 0, 1, 0, 0, 0, 0, 1],
                "target_xy": [2.0, 1.0],
            },
        ]

        rendered = render_dashboard(
            frame,
            observations=observations,
            actions=[-1, 1],
            frame_index=1,
            variant="base",
            episode_id="eval-2001",
        )

        self.assertEqual(rendered.shape, frame.shape)
        self.assertGreater(int(rendered.sum()), 0)
        self.assertEqual(ACTION_LABELS[1], "前进")


if __name__ == "__main__":
    unittest.main()
