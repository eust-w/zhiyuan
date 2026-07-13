"""Turn real episode sidecars into the single machine-readable metric source."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from .metrics import summarize_episode, summarize_runs


def _xy(observation: dict[str, Any]) -> tuple[float, float]:
    pose = observation.get("pose_matrix")
    if not isinstance(pose, list) or len(pose) != 16:
        raise ValueError("sidecar observation has no pose matrix")
    return float(pose[3]), float(pose[7])


def _controller_metrics(sidecar_dir: Path, split: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for path in sorted(sidecar_dir.glob(f"{split}-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        trajectory = data.get("trajectory", [])
        if not trajectory:
            raise ValueError(f"empty trajectory: {path}")
        observations = [item["observation"] for item in trajectory]
        actions = [int(item["action_id"]) for item in trajectory if int(item["action_id"]) != -1]
        distances = [float(obs["distance_to_goal_m"]) for obs in observations]
        path_length = 0.0
        for previous, current in zip(observations, observations[1:]):
            px, py = _xy(previous)
            cx, cy = _xy(current)
            path_length += math.dist((px, py), (cx, cy))
        rows.append(
            summarize_episode(
                episode_id=str(data["episode_id"]),
                distances=distances,
                actions=actions,
                path_length=path_length,
                collisions=sum(1 for obs in observations if obs.get("collision")),
                max_steps=200,
            )
        )
    return summarize_runs(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", default="eval")
    parser.add_argument("--model-available", action="store_true")
    args = parser.parse_args()
    dataset_root = args.dataset_root.expanduser().resolve()
    controller = _controller_metrics(dataset_root / "sidecar", args.split)
    blocked_reason = "StreamVLN model inference was not run; the recorded trajectories are adapter-controller validation only."
    result = {
        "schema_version": "geniesim-streamvln/v1",
        "metric_source": "eval_result.json",
        "official": False,
        "disclaimer": "Reference implementation inspired by the AIMA workflow; not an official course integration.",
        "split": args.split,
        "heldout_episode_ids": [row["episode_id"] for row in controller["episodes_detail"]],
        "controller_validation": controller,
        "base_model": {
            "status": "not_run" if not args.model_available else "pending",
            "reason": blocked_reason,
        },
        "lora_model": {
            "status": "not_run" if not args.model_available else "pending",
            "reason": blocked_reason,
        },
    }
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "controller_episodes": controller["episodes"], "model_status": "not_run"}))


if __name__ == "__main__":
    main()
