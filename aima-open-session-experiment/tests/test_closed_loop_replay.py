from __future__ import annotations

import unittest

from scripts.build_closed_loop_replay import extract_replay_steps


class ClosedLoopReplayTests(unittest.TestCase):
    def test_extract_replay_steps_flattens_generated_actions_and_pose(self) -> None:
        payload = {
            "variant": "base",
            "summary": {
                "episodes_detail": [
                    {
                        "source_episode_id": "eval-2001",
                        "predictions": [{"actions": [3, 1]}],
                        "observations": [
                            {
                                "step_id": 0,
                                "pose_matrix": [1, 0, 0, 0.5, 0, 1, 0, -0.4, 0, 0, 1, 0, 0, 0, 0, 1],
                                "distance_to_goal_m": 4.0,
                                "blocked": False,
                                "collision": False,
                                "target_xy": [-3.45, -0.65],
                            },
                            {
                                "step_id": 1,
                                "pose_matrix": [1, 0, 0, 0.5, 0, 1, 0, -0.4, 0, 0, 1, 0, 0, 0, 0, 1],
                                "distance_to_goal_m": 4.0,
                                "blocked": False,
                                "collision": False,
                                "target_xy": [-3.45, -0.65],
                            },
                            {
                                "step_id": 2,
                                "pose_matrix": [1, 0, 0, 0.5, 0, 1, 0, -0.15, 0, 0, 1, 0, 0, 0, 0, 1],
                                "distance_to_goal_m": 3.9,
                                "blocked": False,
                                "collision": False,
                                "target_xy": [-3.45, -0.65],
                            },
                        ],
                    }
                ]
            },
        }

        replay = extract_replay_steps(payload)

        self.assertEqual(replay["episode_id"], "eval-2001")
        self.assertEqual([step["action_id"] for step in replay["steps"]], [None, 3, 1])
        self.assertEqual(replay["steps"][2]["xy"], [0.5, -0.15])
        self.assertEqual(replay["target_xy"], [-3.45, -0.65])


if __name__ == "__main__":
    unittest.main()
