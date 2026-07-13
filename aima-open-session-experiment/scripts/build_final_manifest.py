#!/usr/bin/env python3
"""Build the final public experiment manifest from verified local artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "experiments/exp02-equivalent-v3/run-manifest.json")
    parser.add_argument("--shutdown-evidence", default="pending")
    args = parser.parse_args()

    required = [
        "experiments/exp02-equivalent-v3/eval_result.json",
        "experiments/exp02-equivalent-v3/dataset-validation.json",
        "experiments/exp02-equivalent-v3/stage0-keyboard.json",
        "experiments/exp02-equivalent-v3/stage0-forward-check.json",
        "experiments/exp02-equivalent-v3/stage2_result_v2.json",
        "artifacts/equivalent-scene/sample.ply",
        "artifacts/equivalent-scene/sample.usda",
        "artifacts/equivalent-scene/sample.usdz",
        "article/抖音-智元布道师图文稿.md",
        "docs/07-PDF逐项验收与等价说明.md",
        "assets/videos/douyin-vln-retrospective-55s.mp4",
        "assets/videos/douyin-vln-retrospective-55s-voiceover.mp4",
        "assets/audio/douyin-vln-voiceover-55s.txt",
        "assets/audio/douyin-vln-voiceover-55s.mp3",
        "assets/audio/douyin-vln-voiceover-55s.srt",
        "assets/screenshots/v3/final-instance-powered-off.jpg",
    ]
    required += [f"assets/carousel/carousel-{index:02d}.jpg" for index in range(1, 21)]
    required += [
        f"assets/media/v3/stage{stage}-{name}.{suffix}"
        for stage, name in [
            (0, "keyboard-and-guard"),
            (1, "train-1001"),
            (2, "training-evidence"),
            (3, "base-2004"),
        ]
        for suffix in ("gif", "mp4")
    ]
    artifacts: dict[str, str] = {}
    for relative in required:
        path = (ROOT / relative).resolve()
        if ROOT not in path.parents or not path.is_file():
            raise SystemExit(f"missing required artifact: {relative}")
        artifacts[relative] = sha256(path)

    manifest = {
        "schema_version": "aima-vln-run-manifest/v2",
        "run_id": "exp02-equivalent-v3-final",
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "classification": "non-official equivalent experiment; transparent failed model evaluation",
        "disclaimer": "Workflow references the AIMA guide but does not use the private course adapter or protocol.",
        "sources": {
            "geniesim_preinstalled_commit": "a04fe4f7fda0ec6e01ab652fa19094008312bf97",
            "geniesim_public_reference": "v3.0.3",
            "streamvln_commit": "e48f6ff7e9201d93aae003e8f64b04c00cec13bc",
            "streamvln_checkpoint_revision": "7b0269ad28e7039a32627b950766c09b5a646f8e",
            "siglip_revision": "9fdffc58afc957d1a03a25b10dba0329ab15c2a3",
        },
        "configuration": {
            "scene": "market_00_g2",
            "robot": "G2 rigid navigation proxy",
            "service": "loopback-only",
            "actions": {"stop": 0, "forward_0_25m": 1, "left_15deg": 2, "right_15deg": 3},
            "train_seeds": "1001-1050",
            "heldout_seeds": "2001-2010",
            "lora": {"r": 8, "alpha": 16, "dropout": 0.05, "epochs": 1, "batch": 1, "learning_rate": 2e-5, "precision": "bf16"},
        },
        "commands": [
            {"name": "unit_tests", "command": "python3 -m unittest discover -s tests -v", "exit_code": 0},
            {"name": "compile", "command": "python3 -m compileall adapter scripts tests", "exit_code": 0},
            {"name": "carousel", "command": "python3 scripts/make_carousel.py --source assets/screenshots/v3 --out-dir assets/carousel --metrics experiments/exp02-equivalent-v3/eval_result.json", "exit_code": 0},
            {"name": "video", "command": "python3 scripts/make_media.py --source assets/screenshots/v3 --out-dir assets/videos --cards-dir assets/carousel --metrics experiments/exp02-equivalent-v3/eval_result.json", "exit_code": 0},
            {"name": "media_decode", "command": "ffmpeg decode checks for all final GIF/MP4 files", "exit_code": 0},
            {"name": "sensitive_scan", "command": "repository public-artifact sensitive-pattern scan", "exit_code": 0},
        ],
        "acceptance": {
            "stage0": "passed with head-depth safety fallback",
            "stage1": "3 smoke + 50 train + 10 heldout passed",
            "stage2": "59 finite non-zero updates; adapter fresh-process reload passed",
            "stage3": "paired base/LoRA evaluation complete; success@0.5m is 0/10 for both",
            "media": "20 images and 55-second H.264 + AAC Chinese voiceover video verified; voice zh-CN-YunyangNeural",
            "shutdown_evidence": args.shutdown_evidence,
        },
        "artifacts_sha256": artifacts,
    }
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "artifacts": len(artifacts)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
