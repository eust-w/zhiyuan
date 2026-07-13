"""StreamVLN-compatible annotation conversion and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DatasetError(ValueError):
    """Raised when a dataset violates the public StreamVLN contract."""


def build_annotation(
    *, episode_id: str, instruction: str, rgb_dir: str, non_stop_actions: list[int]
) -> dict[str, Any]:
    if not episode_id or not instruction.strip() or not rgb_dir:
        raise DatasetError("episode_id, instruction and rgb_dir are required")
    if not non_stop_actions or any(action not in (1, 2, 3) for action in non_stop_actions):
        raise DatasetError("public actions must contain one or more non-stop actions")
    return {
        "id": episode_id,
        "video": rgb_dir,
        "instructions": [instruction.strip()],
        "actions": [-1, *non_stop_actions],
    }


def validate_dataset(
    root: Path,
    *,
    verify_image_bytes: bool = True,
    strict: bool = True,
    annotation_path: Path | None = None,
) -> dict[str, Any]:
    annotation_path = annotation_path or (root / "annotations.json")
    if not annotation_path.is_file():
        raise DatasetError("annotations.json is missing")
    try:
        rows = json.loads(annotation_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DatasetError("annotations.json is not valid JSON") from exc
    if not isinstance(rows, list):
        raise DatasetError("annotations.json must contain a list")
    errors: list[str] = []
    valid = 0
    for index, row in enumerate(rows):
        try:
            if not isinstance(row, dict):
                raise DatasetError("row must be an object")
            actions = row.get("actions")
            if not isinstance(actions, list) or len(actions) < 4 or actions[0] != -1:
                raise DatasetError("actions must start with -1 and contain at least four entries")
            if any(action not in (1, 2, 3, -1) for action in actions) or 0 in actions:
                raise DatasetError("public actions cannot contain STOP=0")
            instructions = row.get("instructions")
            if not isinstance(instructions, list) or not instructions or not all(str(item).strip() for item in instructions):
                raise DatasetError("instructions must be non-empty")
            video = row.get("video")
            if not isinstance(video, str) or not video:
                raise DatasetError("video must be a relative directory")
            rgb_files = sorted((root / video / "rgb").glob("*.jpg"))
            if len(rgb_files) != len(actions):
                raise DatasetError(f"RGB/action mismatch: {len(rgb_files)} != {len(actions)}")
            if verify_image_bytes and any(path.stat().st_size == 0 for path in rgb_files):
                raise DatasetError("empty RGB file")
            valid += 1
        except (DatasetError, OSError) as exc:
            errors.append(f"row {index}: {exc}")
    report = {"episodes": len(rows), "valid": valid, "invalid": len(errors), "errors": errors}
    if strict and errors:
        raise DatasetError("dataset validation failed: " + "; ".join(errors))
    return report
