import unittest

from adapter.assemble_eval_result import assemble


def summary(ids):
    return {"episodes_detail": [{"episode_id": value} for value in ids]}


class AssembleEvalResultTests(unittest.TestCase):
    def test_requires_identical_episode_order(self):
        with self.assertRaisesRegex(ValueError, "IDs differ"):
            assemble(
                controller=summary(["eval-1", "eval-2"]),
                base={"variant": "base", "episode_ids": ["eval-1", "eval-2"]},
                lora={"variant": "lora", "episode_ids": ["eval-2", "eval-1"]},
            )

    def test_builds_single_metric_source(self):
        result = assemble(
            controller=summary(["eval-1"]),
            base={"variant": "base", "episode_ids": ["eval-1"], "summary": {}},
            lora={"variant": "lora", "episode_ids": ["eval-1"], "summary": {}},
        )
        self.assertEqual(result["metric_source"], "eval_result.json")
        self.assertTrue(result["same_heldout_batch"])
        self.assertEqual(result["heldout_episode_ids"], ["eval-1"])


if __name__ == "__main__":
    unittest.main()
