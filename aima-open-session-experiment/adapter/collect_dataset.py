"""Collect deterministic StreamVLN-shaped episodes from the loopback adapter.

The collector intentionally uses only the public HTTP contract.  It does not
import Isaac or StreamVLN, so it can run in the persistent Python 3.9
environment while Isaac owns its own Python 3.11 process.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .dataset import build_annotation, validate_dataset


TRAIN_INSTRUCTIONS = (
    "Go to the red target marker.",
    "Navigate to the red marker.",
    "Move to the red target sign.",
    "Find the red marker and stop beside it.",
    "Approach the red navigation target.",
)
EVAL_INSTRUCTIONS = (
    "Walk toward the red beacon and stop.",
    "Reach the red goal marker.",
)


def _request(base_url: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        base_url.rstrip("/") + path,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urlopen(request, timeout=90) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"adapter request failed: {path}: {exc}") from exc
    if not isinstance(result, dict):
        raise RuntimeError(f"adapter returned a non-object for {path}")
    if "error" in result:
        raise RuntimeError(f"adapter error for {path}: {result['error']}")
    return result


def _pose_xy_yaw(observation: dict[str, Any]) -> tuple[float, float, float]:
    matrix = observation.get("pose_matrix")
    if not isinstance(matrix, list) or len(matrix) != 16:
        raise RuntimeError("observation has no 4x4 pose_matrix")
    return float(matrix[3]), float(matrix[7]), math.atan2(float(matrix[4]), float(matrix[0]))


def _wrap_angle(angle: float) -> float:
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def _choose_action(observation: dict[str, Any]) -> int:
    """Greedy 24-direction controller used only for deterministic collection."""

    target = observation.get("target_xy")
    if not isinstance(target, list) or len(target) != 2:
        raise RuntimeError("observation is missing target_xy")
    x, y, yaw = _pose_xy_yaw(observation)
    desired = math.atan2(float(target[1]) - y, float(target[0]) - x)
    error = _wrap_angle(desired - yaw)
    # One turn is exactly 15 degrees.  Turn until the target is inside the
    # forward action's half-bin, then advance by the fixed 0.25 m primitive.
    if abs(error) > math.pi / 24.0:
        return 2 if error > 0 else 3
    return 1


def _copy_observation(root: Path, dataset_episode: Path, observation: dict[str, Any], frame_index: int) -> dict[str, str]:
    rgb_source = root / str(observation["rgb_path"])
    depth_source = root / str(observation["depth_path"])
    if not rgb_source.is_file() or not depth_source.is_file():
        raise RuntimeError(f"observation files are missing: {rgb_source} / {depth_source}")
    rgb_dir = dataset_episode / "rgb"
    depth_dir = dataset_episode / "depth"
    rgb_dir.mkdir(parents=True, exist_ok=True)
    depth_dir.mkdir(parents=True, exist_ok=True)
    rgb_target = rgb_dir / f"{frame_index:04d}.jpg"
    depth_target = depth_dir / f"{frame_index:04d}.npy"
    shutil.copy2(rgb_source, rgb_target)
    shutil.copy2(depth_source, depth_target)
    return {"rgb": str(rgb_target), "depth": str(depth_target)}


def collect_episode(
    *,
    base_url: str,
    root: Path,
    dataset_root: Path,
    split: str,
    episode_id: str,
    seed: int,
    instruction: str,
    max_steps: int,
    retry_sleep_s: float = 0.2,
) -> dict[str, Any]:
    reset = _request(
        base_url,
        "/v1/episodes/reset",
        {
            "schema_version": "geniesim-streamvln/v1",
            "episode_id": episode_id,
            "seed": seed,
            "instruction": instruction,
            "target_id": "red-target-marker",
        },
    )
    episode_dir = dataset_root / split / episode_id
    if episode_dir.exists():
        shutil.rmtree(episode_dir)
    public_observations: list[dict[str, Any]] = [reset]
    non_stop_actions: list[int] = []
    trajectory: list[dict[str, Any]] = [{"action_id": -1, "observation": reset}]
    stopped = False
    for index in range(max_steps):
        if float(reset.get("distance_to_goal_m", 1e9)) <= 0.5:
            break
        action_id = _choose_action(reset)
        response = _request(
            base_url,
            f"/v1/episodes/{episode_id}/step",
            {"request_id": f"{episode_id}-{index:04d}", "action_id": action_id},
        )
        non_stop_actions.append(action_id)
        public_observations.append(response)
        trajectory.append({"action_id": action_id, "observation": response})
        reset = response
        if response.get("terminated") or response.get("truncated"):
            break
        if response.get("blocked"):
            # A blank fallback grid should never block, but retain an explicit
            # recovery action for future USD-AABB runs.
            time.sleep(retry_sleep_s)
    # STOP is retained only in the sidecar. Public StreamVLN annotations end
    # before STOP and therefore have exactly one RGB frame per action entry.
    stop_response = _request(
        base_url,
        f"/v1/episodes/{episode_id}/step",
        {"request_id": f"{episode_id}-stop", "action_id": 0},
    )
    trajectory.append({"action_id": 0, "observation": stop_response})
    stopped = bool(stop_response.get("terminated"))
    _request(base_url, f"/v1/episodes/{episode_id}/close", {})

    copied: list[dict[str, str]] = []
    for frame_index, observation in enumerate(public_observations):
        copied.append(_copy_observation(root, episode_dir, observation, frame_index))
    sidecar_dir = dataset_root / "sidecar"
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    sidecar = {
        "schema_version": "geniesim-streamvln/v1",
        "episode_id": episode_id,
        "split": split,
        "seed": seed,
        "instruction": instruction,
        "target_id": "red-target-marker",
        "actions": [-1, *non_stop_actions, 0],
        "public_frame_count": len(public_observations),
        "stopped": stopped,
        "trajectory": trajectory,
        "copied_files": copied,
        "nonofficial": True,
    }
    (sidecar_dir / f"{episode_id}.json").write_text(json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "episode_id": episode_id,
        "split": split,
        "seed": seed,
        "steps": len(non_stop_actions),
        "stopped": stopped,
        "distance_to_goal_m": float(stop_response.get("distance_to_goal_m", 0.0)),
        "collisions": sum(1 for item in trajectory if item["observation"].get("collision")),
    }


def _write_annotations(dataset_root: Path, split: str, records: list[dict[str, Any]], instructions: dict[str, str]) -> Path:
    rows: list[dict[str, Any]] = []
    for record in records:
        episode_id = str(record["episode_id"])
        sidecar = json.loads((dataset_root / "sidecar" / f"{episode_id}.json").read_text(encoding="utf-8"))
        rows.append(
            build_annotation(
                episode_id=episode_id,
                instruction=instructions[episode_id],
                # annotations.json lives inside the split directory; the
                # public StreamVLN loader resolves video relative to that
                # directory (and prepends --video_folder itself).
                rgb_dir=episode_id,
                non_stop_actions=[int(action) for action in sidecar["actions"][1:-1]],
            )
        )
    path = dataset_root / split / "annotations.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5802")
    parser.add_argument("--root", type=Path, required=True, help="experiment root used by the adapter")
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--split", choices=("smoke", "train", "eval"), required=True)
    parser.add_argument("--start-seed", type=int, required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--instruction", default=None, help="override the deterministic split template")
    args = parser.parse_args()
    if args.count <= 0:
        raise SystemExit("--count must be positive")
    root = args.root.expanduser().resolve()
    dataset_root = args.dataset_root.expanduser().resolve()
    records: list[dict[str, Any]] = []
    instructions: dict[str, str] = {}
    for offset in range(args.count):
        seed = args.start_seed + offset
        episode_id = f"{args.split}-{seed:04d}"
        if args.instruction:
            instruction = args.instruction
        elif args.split == "eval":
            instruction = EVAL_INSTRUCTIONS[offset % len(EVAL_INSTRUCTIONS)]
        else:
            instruction = TRAIN_INSTRUCTIONS[offset % len(TRAIN_INSTRUCTIONS)]
        print(json.dumps({"event": "episode_start", "episode_id": episode_id, "seed": seed}), flush=True)
        record = collect_episode(
            base_url=args.base_url,
            root=root,
            dataset_root=dataset_root,
            split=args.split,
            episode_id=episode_id,
            seed=seed,
            instruction=instruction,
            max_steps=args.max_steps,
        )
        records.append(record)
        instructions[episode_id] = instruction
        print(json.dumps({"event": "episode_done", **record}), flush=True)
    if args.split != "smoke":
        _write_annotations(dataset_root, args.split, records, instructions)
        report = validate_dataset(
            dataset_root / args.split,
            annotation_path=dataset_root / args.split / "annotations.json",
            verify_image_bytes=True,
            strict=False,
        )
        (dataset_root / f"{args.split}-collection-report.json").write_text(
            json.dumps({"records": records, "validation": report}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps({"event": "dataset_validated", **report}), flush=True)


if __name__ == "__main__":
    main()
