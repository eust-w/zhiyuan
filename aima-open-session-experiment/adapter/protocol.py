"""Small, dependency-free HTTP/data contract for the non-official adapter."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


class ProtocolError(ValueError):
    """Raised when a request or response violates the adapter contract."""


ACTIONS = {0: "stop", 1: "forward", 2: "left", 3: "right"}
SCHEMA_VERSION = "geniesim-streamvln/v1"


def _required_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ProtocolError(f"{key} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True)
class EpisodeReset:
    schema_version: str
    episode_id: str
    seed: int
    instruction: str
    target_id: str

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> "EpisodeReset":
        schema_version = payload.get("schema_version", SCHEMA_VERSION)
        if schema_version != SCHEMA_VERSION:
            raise ProtocolError(f"unsupported schema_version: {schema_version!r}")
        seed = payload.get("seed")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ProtocolError("seed must be an integer")
        return cls(
            schema_version=SCHEMA_VERSION,
            episode_id=_required_string(payload, "episode_id"),
            seed=seed,
            instruction=_required_string(payload, "instruction"),
            target_id=_required_string(payload, "target_id"),
        )


@dataclass(frozen=True)
class EpisodeStep:
    request_id: str
    action_id: int

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> "EpisodeStep":
        request_id = _required_string(payload, "request_id")
        action_id = payload.get("action_id")
        if isinstance(action_id, bool) or not isinstance(action_id, int) or action_id not in ACTIONS:
            raise ProtocolError("action_id must be one of 0, 1, 2, 3")
        return cls(request_id=request_id, action_id=action_id)


def safe_relative_path(root: Path, candidate: Path) -> str:
    """Return a POSIX path only when candidate is inside the experiment root."""

    root_resolved = root.expanduser().resolve()
    candidate_path = Path(candidate).expanduser()
    if not candidate_path.is_absolute():
        raise ProtocolError("media paths must be absolute before validation")
    candidate_resolved = candidate_path.resolve(strict=False)
    try:
        relative = candidate_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ProtocolError("media path escapes experiment root") from exc
    return relative.as_posix()


def build_observation(
    *,
    episode_id: str,
    step_id: int,
    rgb_path: str,
    depth_path: str,
    pose_matrix: list[float],
    distance_to_goal_m: float,
    collision: bool,
    blocked: bool,
    terminated: bool,
    truncated: bool,
) -> dict[str, Any]:
    if not episode_id or step_id < 0:
        raise ProtocolError("episode_id and step_id are invalid")
    if len(pose_matrix) != 16 or not all(math.isfinite(float(value)) for value in pose_matrix):
        raise ProtocolError("pose_matrix must contain 16 finite values")
    if not math.isfinite(float(distance_to_goal_m)) or distance_to_goal_m < 0:
        raise ProtocolError("distance_to_goal_m must be a finite non-negative number")
    return {
        "schema_version": SCHEMA_VERSION,
        "episode_id": episode_id,
        "step_id": step_id,
        "rgb_path": rgb_path,
        "depth_path": depth_path,
        "pose_matrix": [float(value) for value in pose_matrix],
        "distance_to_goal_m": float(distance_to_goal_m),
        "collision": bool(collision),
        "blocked": bool(blocked),
        "terminated": bool(terminated),
        "truncated": bool(truncated),
    }

