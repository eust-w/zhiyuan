import unittest

from adapter.metrics import summarize_episode, summarize_runs


class MetricsTests(unittest.TestCase):
    def test_episode_success_requires_stop_inside_radius(self):
        result = summarize_episode(
            episode_id="e1",
            distances=[2.0, 1.0, 0.4],
            actions=[1, 1, 0],
            path_length=0.5,
            collisions=1,
            max_steps=200,
        )
        self.assertTrue(result["success_0_5"])
        self.assertTrue(result["success_3"])
        self.assertEqual(result["action_counts"]["stop"], 1)
        self.assertEqual(result["collisions"], 1)

    def test_summary_reports_all_runs_without_hiding_failures(self):
        rows = [
            summarize_episode("e1", [2.0, 0.4], [1, 0], 0.25, 0, 200),
            summarize_episode("e2", [2.0, 1.8], [1, 1], 0.5, 2, 200),
        ]
        summary = summarize_runs(rows)
        self.assertEqual(summary["episodes"], 2)
        self.assertEqual(summary["success_0_5"], 1)
        self.assertEqual(summary["collisions"], 2)


if __name__ == "__main__":
    unittest.main()

