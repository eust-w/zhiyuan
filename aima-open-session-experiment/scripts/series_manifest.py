"""Load and validate the evidence-driven media series manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "aima-vln-series/v1"
SOURCE_TYPES = {
    "real_recording",
    "real_evidence",
    "ai_diagram",
    "metric_animation",
    "title_card",
}
LAYOUTS = {"landscape", "portrait"}


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("series manifest must be a JSON object")
    data["_manifest_path"] = str(path.resolve())
    return data


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def validate_manifest(manifest: dict[str, Any], root: Path) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    target = manifest.get("real_ratio_target")
    if not isinstance(target, (int, float)) or target < 0.75 or target > 1:
        errors.append("real_ratio_target must be between 0.75 and 1.0")
    episodes = manifest.get("episodes")
    if not isinstance(episodes, list) or len(episodes) != 4:
        errors.append("episodes must contain exactly four entries")
        episodes = episodes if isinstance(episodes, list) else []
    ids = [episode.get("episode") for episode in episodes if isinstance(episode, dict)]
    expected = {"stage0", "stage1", "stage2", "stage3"}
    if set(ids) != expected:
        errors.append("episodes must be stage0, stage1, stage2 and stage3")
    for episode in episodes:
        if not isinstance(episode, dict):
            errors.append("episode entries must be objects")
            continue
        episode_id = episode.get("episode", "<missing>")
        segments = episode.get("segments")
        if not isinstance(segments, list) or not segments:
            errors.append(f"{episode_id}: segments must be a non-empty list")
            continue
        for segment in segments:
            if not isinstance(segment, dict):
                errors.append(f"{episode_id}: segment must be an object")
                continue
            segment_id = segment.get("segment_id", "<missing>")
            source = segment.get("source")
            if not isinstance(source, str) or not source:
                errors.append(f"{segment_id}: source is required")
            else:
                source_path = (root / source).resolve()
                if not _is_within(source_path, root):
                    errors.append(f"{segment_id}: source escapes manifest root")
                elif not source_path.is_file():
                    errors.append(f"{segment_id}: source does not exist: {source}")
            source_type = segment.get("source_type")
            if source_type not in SOURCE_TYPES:
                errors.append(f"{segment_id}: source_type is invalid")
            evidence_ref = segment.get("evidence_ref")
            if not isinstance(evidence_ref, str) or not evidence_ref.strip():
                errors.append(f"{segment_id}: evidence_ref is required")
            duration = segment.get("duration_s")
            if not isinstance(duration, (int, float)) or duration <= 0:
                errors.append(f"{segment_id}: duration_s must be positive")
            if segment.get("layout") not in LAYOUTS:
                errors.append(f"{segment_id}: layout must be landscape or portrait")
            if not isinstance(segment.get("narration"), str) or not segment["narration"].strip():
                errors.append(f"{segment_id}: narration is required")
            if not isinstance(segment.get("subtitle"), list) or not segment["subtitle"]:
                errors.append(f"{segment_id}: subtitle must be a non-empty list")
    return errors


def metric_snapshot(eval_path: Path) -> dict[str, Any]:
    data = json.loads(eval_path.read_text(encoding="utf-8"))
    variants: dict[str, Any] = {}
    for name, key in (("base", "base_model"), ("lora", "lora_model")):
        evaluation = data[key]["model_evaluation"]
        summary = evaluation["summary"]
        required = ("success_0_5", "success_3", "collisions", "mean_final_distance_to_goal", "mean_path_length", "mean_steps")
        missing = [field for field in required if field not in summary]
        if missing:
            raise ValueError(f"{key} summary missing: {', '.join(missing)}")
        variants[name] = {field: summary[field] for field in required}
    return {
        "schema_version": data.get("schema_version"),
        "heldout_episode_ids": data.get("heldout_episode_ids", []),
        "variants": variants,
    }
