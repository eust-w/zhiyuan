"""Assemble the single paired Stage 3 metric source with strict ID checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .evaluate_sidecars import _controller_metrics


def assemble(*, controller: dict[str, Any], base: dict[str, Any], lora: dict[str, Any]) -> dict[str, Any]:
    controller_ids = [str(row["episode_id"]) for row in controller["episodes_detail"]]
    base_ids = [str(value) for value in base.get("episode_ids", [])]
    lora_ids = [str(value) for value in lora.get("episode_ids", [])]
    if not controller_ids or controller_ids != base_ids or base_ids != lora_ids:
        raise ValueError(
            f"paired evaluation IDs differ: controller={controller_ids}, base={base_ids}, lora={lora_ids}"
        )
    if base.get("variant") != "base" or lora.get("variant") != "lora":
        raise ValueError("variant labels must be base and lora")
    return {
        "schema_version": "geniesim-streamvln/v1",
        "metric_source": "eval_result.json",
        "official": False,
        "disclaimer": "AIMA workflow reference; self-captured equivalent assets; not an official course integration.",
        "split": "eval",
        "heldout_episode_ids": controller_ids,
        "same_heldout_batch": True,
        "controller_validation": controller,
        "base_model": {
            "status": "passed",
            "reason": "StreamVLN base actions were executed by the live loopback GenieSim adapter.",
            "model_evaluation": base,
        },
        "lora_model": {
            "status": "passed",
            "reason": "The newly trained LoRA actions were executed on the identical held-out episodes.",
            "model_evaluation": lora,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--lora", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    controller = _controller_metrics(args.dataset_root.expanduser().resolve() / "sidecar", "eval")
    base = json.loads(args.base.expanduser().resolve().read_text(encoding="utf-8"))
    lora = json.loads(args.lora.expanduser().resolve().read_text(encoding="utf-8"))
    result = assemble(controller=controller, base=base, lora=lora)
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "episodes": len(result["heldout_episode_ids"])}))


if __name__ == "__main__":
    main()
