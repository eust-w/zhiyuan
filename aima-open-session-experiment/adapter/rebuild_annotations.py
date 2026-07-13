"""Rebuild public annotations from already collected sidecars."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .dataset import build_annotation, validate_dataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--split", choices=("train", "eval"), required=True)
    args = parser.parse_args()
    root = args.dataset_root.expanduser().resolve()
    split_root = root / args.split
    sidecars = sorted((root / "sidecar").glob(f"{args.split}-*.json"))
    rows = []
    for path in sidecars:
        data = json.loads(path.read_text(encoding="utf-8"))
        rows.append(
            build_annotation(
                episode_id=str(data["episode_id"]),
                instruction=str(data["instruction"]),
                rgb_dir=str(data["episode_id"]),
                non_stop_actions=[int(action) for action in data["actions"][1:-1]],
            )
        )
    annotation_path = split_root / "annotations.json"
    annotation_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    report = validate_dataset(split_root, annotation_path=annotation_path, verify_image_bytes=True, strict=True)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
