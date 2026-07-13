"""Conservative 2-D occupancy and discrete SE(2) A* utilities."""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Iterable


Pose2D = tuple[int, int, int]


@dataclass
class OccupancyGrid:
    resolution: float
    blocked: set[tuple[int, int]] = field(default_factory=set)
    bounds: tuple[int, int, int, int] | None = None
    forward_step_m: float = 0.25

    def __post_init__(self) -> None:
        if self.resolution <= 0:
            raise ValueError("resolution must be positive")
        if self.forward_step_m <= 0:
            raise ValueError("forward_step_m must be positive")
        self.blocked = set(self.blocked)

    def in_bounds(self, cell: tuple[int, int]) -> bool:
        if self.bounds is None:
            return True
        min_x, max_x, min_y, max_y = self.bounds
        return min_x <= cell[0] <= max_x and min_y <= cell[1] <= max_y

    def is_free(self, cell: tuple[int, int]) -> bool:
        return self.in_bounds(cell) and cell not in self.blocked

    def world_to_cell(self, x: float, y: float) -> tuple[int, int]:
        return round(x / self.resolution), round(y / self.resolution)

    def cell_to_world(self, cell: tuple[int, int]) -> tuple[float, float]:
        return cell[0] * self.resolution, cell[1] * self.resolution


def footprint_cells(
    *,
    center: tuple[int, int],
    yaw_bin: int,
    half_length: float,
    half_width: float,
    resolution: float,
    yaw_bins: int = 24,
) -> set[tuple[int, int]]:
    """Rasterize a conservative oriented rectangle around a grid cell."""

    radius = math.ceil((math.hypot(half_length, half_width) + resolution) / resolution)
    yaw = (yaw_bin % yaw_bins) * 2 * math.pi / yaw_bins
    cos_yaw, sin_yaw = math.cos(yaw), math.sin(yaw)
    cells: set[tuple[int, int]] = set()
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            local_x = (dx * cos_yaw + dy * sin_yaw) * resolution
            local_y = (-dx * sin_yaw + dy * cos_yaw) * resolution
            if abs(local_x) <= half_length + resolution / 2 and abs(local_y) <= half_width + resolution / 2:
                cells.add((center[0] + dx, center[1] + dy))
    return cells


def _step_for_yaw(yaw_bin: int, yaw_bins: int = 24) -> tuple[int, int]:
    angle = (yaw_bin % yaw_bins) * 2 * math.pi / yaw_bins
    return round(math.cos(angle)), round(math.sin(angle))


def _neighbors(grid: OccupancyGrid, state: Pose2D) -> Iterable[tuple[Pose2D, float]]:
    x, y, yaw = state
    yield (x, y, (yaw + 1) % 24), 0.25
    yield (x, y, (yaw - 1) % 24), 0.25
    dx, dy = _step_for_yaw(yaw)
    stride = max(1, round(grid.forward_step_m / grid.resolution))
    cells = [(x + dx * offset, y + dy * offset) for offset in range(1, stride + 1)]
    if all(grid.is_free(cell) for cell in cells):
        forward = cells[-1]
        yield (forward[0], forward[1], yaw), 1.0


def astar(grid: OccupancyGrid, start: Pose2D, goal: Pose2D) -> list[Pose2D] | None:
    """Find a collision-free path. Goal orientation is part of the state."""

    if grid.bounds is None:
        margin = max(20, round(2.0 / grid.resolution))
        effective_grid = OccupancyGrid(
            resolution=grid.resolution,
            blocked=grid.blocked,
            bounds=(
                min(start[0], goal[0]) - margin,
                max(start[0], goal[0]) + margin,
                min(start[1], goal[1]) - margin,
                max(start[1], goal[1]) + margin,
            ),
            forward_step_m=grid.forward_step_m,
        )
    else:
        effective_grid = grid
    if not effective_grid.is_free(start[:2]) or not effective_grid.is_free(goal[:2]):
        return None
    frontier: list[tuple[float, int, Pose2D]] = []
    counter = 0
    heapq.heappush(frontier, (0.0, counter, start))
    came_from: dict[Pose2D, Pose2D | None] = {start: None}
    cost_so_far: dict[Pose2D, float] = {start: 0.0}
    while frontier:
        _, _, current = heapq.heappop(frontier)
        if current == goal:
            path: list[Pose2D] = []
            cursor: Pose2D | None = current
            while cursor is not None:
                path.append(cursor)
                cursor = came_from[cursor]
            return list(reversed(path))
        for neighbor, step_cost in _neighbors(effective_grid, current):
            new_cost = cost_so_far[current] + step_cost
            if new_cost >= cost_so_far.get(neighbor, float("inf")):
                continue
            cost_so_far[neighbor] = new_cost
            came_from[neighbor] = current
            distance = abs(goal[0] - neighbor[0]) + abs(goal[1] - neighbor[1])
            turn_distance = min((goal[2] - neighbor[2]) % 24, (neighbor[2] - goal[2]) % 24)
            counter += 1
            heapq.heappush(frontier, (new_cost + distance + 0.1 * turn_distance, counter, neighbor))
    return None
