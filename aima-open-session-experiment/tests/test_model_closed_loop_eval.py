import unittest

from adapter.model_closed_loop_eval import StreamVLNRunner, path_length, pose_xy


class ModelClosedLoopEvalTests(unittest.TestCase):
    def test_parser_keeps_model_action_order_and_falls_back_to_stop(self):
        self.assertEqual(StreamVLNRunner.parse_actions("assistant\n→→↑←STOP"), [3, 1, 2, 0])
        self.assertEqual(StreamVLNRunner.parse_actions("no valid action"), [0])

    def test_pose_and_path_length_use_xy_translation(self):
        first = {"pose_matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]}
        second = {"pose_matrix": [1, 0, 0, 1, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]}
        third = {"pose_matrix": [1, 0, 0, 1, 0, 1, 0, 2, 0, 0, 1, 0, 0, 0, 0, 1]}
        self.assertEqual(pose_xy(third), (1.0, 2.0))
        self.assertAlmostEqual(path_length([first, second, third]), 3.0)


if __name__ == "__main__":
    unittest.main()
