import math
import unittest

import numpy as np

from adapter.isaac_backend import (
    action_pose,
    depth_forward_blocked,
    pinhole_intrinsics,
    pose_matrix_xy_yaw,
    quat_wxyz_from_yaw,
    seeded_start_pose,
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
        self.assertEqual(action_pose((1.0, 2.0, 0), 4), (0.75, 2.0, 0))
        self.assertIsNone(action_pose((1.0, 2.0, 0), 0))

    def test_pinhole_intrinsics(self):
        matrix = pinhole_intrinsics(640, 400, 24.0, 32.0, 20.0)
        self.assertEqual(matrix, [480.0, 0.0, 319.5, 0.0, 480.0, 199.5, 0.0, 0.0, 1.0])

    def test_depth_forward_guard_uses_robust_center_percentile(self):
        clear = np.full((100, 160), 2.0, dtype=np.float32)
        self.assertFalse(depth_forward_blocked(clear))
        near = clear.copy()
        near[35:85, 48:112] = 0.30
        self.assertTrue(depth_forward_blocked(near))
        one_bad_pixel = clear.copy()
        one_bad_pixel[50, 80] = 0.01
        self.assertFalse(depth_forward_blocked(one_bad_pixel))

    def test_seeded_starts_are_bounded_and_unique(self):
        poses = [seeded_start_pose((1.0, 2.0, 0), seed) for seed in range(1001, 1051)]
        self.assertEqual(len(set(poses)), 50)
        self.assertTrue(all(0.5 <= pose[0] <= 1.5 for pose in poses))
        self.assertTrue(all(1.75 <= pose[1] <= 2.25 for pose in poses))
        self.assertTrue(all(0 <= pose[2] < 24 for pose in poses))


if __name__ == "__main__":
    unittest.main()
