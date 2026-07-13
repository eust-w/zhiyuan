"""Metrics shared by base and LoRA evaluation."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable


ACTION_NAMES = {0: "stop", 1: "forward", 2: "left", 3: "right"}


def summarize_episode(
    episode_id: str,
    distances: Iterable[float],
    actions: Iterable[int],
    path_length: float,
    collisions: int,
    max_steps: int,
) -> dict[str, Any]:
    distance_values = [float(value) for value in distances]
    action_values = [int(value) for value in actions]
    if not distance_values:
        raise ValueError("at least one distance is required")
    counts = Counter(ACTION_NAMES.get(action, "invalid") for action in action_values)
    final_distance = distance_values[-1]
    stopped = 0 in action_values
    success_0_5 = bool(stopped and final_distance <= 0.5)
    success_3 = bool(stopped and final_distance <= 3.0)
    shortest_path = max(distance_values[0], 0.0)
    path_denominator = max(float(path_length), shortest_path, 1e-9)
    return {
        "episode_id": episode_id,
        "success_0_5": success_0_5,
        "success_3": success_3,
        "oracle_success_0_5": bool(min(distance_values) <= 0.5),
        "oracle_success_3": bool(min(distance_values) <= 3.0),
        "final_distance_to_goal": final_distance,
        "min_distance_to_goal": min(distance_values),
        "path_length": float(path_length),
        "shortest_path_length": shortest_path,
        "spl_0_5": float(shortest_path / path_denominator) if success_0_5 else 0.0,
        "spl_3": float(shortest_path / path_denominator) if success_3 else 0.0,
        "steps": len(action_values),
        "collisions": int(collisions),
        "truncated": len(action_values) >= max_steps and not stopped,
        "action_counts": {name: counts.get(name, 0) for name in ACTION_NAMES.values()},
    }


def summarize_runs(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("at least one episode is required")
    total = len(rows)
    return {
        "episodes": total,
        "success_0_5": sum(bool(row["success_0_5"]) for row in rows),
        "success_3": sum(bool(row["success_3"]) for row in rows),
        "oracle_success_0_5": sum(bool(row["oracle_success_0_5"]) for row in rows),
        "oracle_success_3": sum(bool(row["oracle_success_3"]) for row in rows),
        "collisions": sum(int(row["collisions"]) for row in rows),
        "mean_final_distance_to_goal": sum(float(row["final_distance_to_goal"]) for row in rows) / total,
        "mean_min_distance_to_goal": sum(float(row["min_distance_to_goal"]) for row in rows) / total,
        "mean_path_length": sum(float(row["path_length"]) for row in rows) / total,
        "mean_spl_0_5": sum(float(row["spl_0_5"]) for row in rows) / total,
        "mean_spl_3": sum(float(row["spl_3"]) for row in rows) / total,
        "mean_steps": sum(int(row["steps"]) for row in rows) / total,
        "episodes_detail": rows,
    }
