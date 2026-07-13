import tempfile
import unittest
from pathlib import Path

import numpy as np

from adapter.equivalent_assets import project_rgbd, voxel_downsample, write_ply


class EquivalentAssetsTest(unittest.TestCase):
    def test_project_center_pixel_along_camera_minus_z(self):
        rgb = np.zeros((3, 3, 3), dtype=np.uint8)
        rgb[1, 1] = [10, 20, 30]
        depth = np.full((3, 3), np.nan, dtype=np.float32)
        depth[1, 1] = 2.0
        points, colors = project_rgbd(
            rgb,
            depth,
            [2.0, 0.0, 1.0, 0.0, 2.0, 1.0, 0.0, 0.0, 1.0],
            np.eye(4).reshape(-1),
            stride=1,
        )
        np.testing.assert_allclose(points, [[0.0, 0.0, -2.0]])
        np.testing.assert_array_equal(colors, [[10, 20, 30]])

    def test_voxel_and_binary_ply(self):
        points = np.asarray([[0.0, 0.0, 0.0], [0.01, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=np.float32)
        colors = np.asarray([[1, 2, 3], [4, 5, 6], [7, 8, 9]], dtype=np.uint8)
        sampled_points, sampled_colors = voxel_downsample(points, colors, 0.1)
        self.assertEqual(len(sampled_points), 2)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.ply"
            write_ply(path, sampled_points, sampled_colors)
            self.assertIn(b"element vertex 2", path.read_bytes()[:256])


if __name__ == "__main__":
    unittest.main()
