import math
import unittest

from adapter.isaac_backend import (
    action_pose,
    pose_matrix_xy_yaw,
    quat_wxyz_from_yaw,
)


class IsaacBackendPureHelpersTest(unittest.TestCase):
    def test_pose_matrix_and_quaternion(self):
        matrix = pose_matrix_xy_yaw(1.25, -0.5, math.pi / 2)
        self.assertEqual(len(matrix), 16)
        self.assertAlmostEqual(matrix[0], 0.0, places=6)
        self.assertAlmostEqual(matrix[1], -1.0, places=6)
        self.assertAlmostEqual(matrix[4], 1.0, places=6)
        self.assertAlmostEqual(matrix[5], 0.0, places=6)
        self.assertEqual(matrix[3], 1.25)
        self.assertEqual(matrix[7], -0.5)
        self.assertAlmostEqual(quat_wxyz_from_yaw(math.pi)[0], 0.0, places=6)
        self.assertEqual(quat_wxyz_from_yaw(math.pi)[1:], (0.0, 0.0, 1.0))

    def test_action_pose(self):
        self.assertEqual(action_pose((1.0, 2.0, 0), 1), (1.25, 2.0, 0))
        self.assertEqual(action_pose((1.0, 2.0, 0), 2), (1.0, 2.0, 1))
        self.assertEqual(action_pose((1.0, 2.0, 0), 3), (1.0, 2.0, 23))
        self.assertIsNone(action_pose((1.0, 2.0, 0), 0))


if __name__ == "__main__":
    unittest.main()
