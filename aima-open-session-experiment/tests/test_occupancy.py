import unittest

from adapter.occupancy import OccupancyGrid, Pose2D, astar, footprint_cells


class OccupancyTests(unittest.TestCase):
    def test_blocked_step_does_not_appear_in_path(self):
        blocked = {(1, 0), (1, 1), (1, -1)}
        grid = OccupancyGrid(resolution=0.25, blocked=blocked)
        path = astar(grid, (0, 0, 0), (2, 0, 0))
        self.assertIsNotNone(path)
        self.assertTrue(all((x, y) not in blocked for x, y, _ in path))

    def test_astar_returns_none_when_wall_splits_bounds(self):
        blocked = {(1, y) for y in range(-3, 4)}
        grid = OccupancyGrid(resolution=1.0, blocked=blocked, bounds=(-2, 2, -3, 3))
        self.assertIsNone(astar(grid, (-1, 0, 0), (2, 0, 0)))

    def test_footprint_inflation_is_conservative(self):
        cells = footprint_cells(center=(0, 0), yaw_bin=0, half_length=0.2, half_width=0.15, resolution=0.05)
        self.assertIn((0, 0), cells)
        self.assertGreater(len(cells), 20)


if __name__ == "__main__":
    unittest.main()
