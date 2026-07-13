"""Prepare and optionally execute the official StreamVLN LoRA command.

This wrapper makes the four required gates explicit: dataset-only, one-batch
forward/backward, full training, and adapter reload.  It never fabricates an
adapter when a dependency or checkpoint is missing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .dataset import validate_dataset


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _last_error(text: str) -> str | None:
    """Extract the final concise exception line from a captured traceback."""
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith(("RuntimeError:", "ValueError:", "AttributeError:", "ImportError:", "ModuleNotFoundError:", "UnboundLocalError:")):
            return line
    return None


def build_command(*, python: str, repo: Path, checkpoint: Path, vision: Path, data: Path, output: Path, max_steps: int | None = None) -> list[str]:
    command = [
        python,
        str(repo / "streamvln" / "streamvln_train.py"),
        "--model_name_or_path", str(checkpoint),
        "--vision_tower", str(vision),
        "--video_folder", str(data),
        "--version", "qwen",
        "--mm_tunable_parts", "mm_lora_layer",
        "--lora_enable", "True",
        "--lora_r", "8",
        "--lora_alpha", "16",
        "--lora_dropout", "0.05",
        "--num_train_epochs", "1",
        "--per_device_train_batch_size", "1",
        "--gradient_accumulation_steps", "1",
        "--learning_rate", "2e-5",
        "--bf16", "True",
        "--gradient_checkpointing", "True",
        "--attn_implementation", "sdpa",
        "--num_frames", "32",
        "--num_history", "8",
        "--num_future_steps", "4",
        "--model_max_length", "4096",
        "--output_dir", str(output),
        "--report_to", "none",
        "--logging_steps", "1",
        "--save_strategy", "no",
    ]
    if max_steps is not None:
        command += ["--max_steps", str(max_steps)]
    return command


def _qwen_compat_checkpoint(checkpoint: Path) -> Path:
    """Return a stable path whose name selects StreamVLN's Qwen tokenizer branch.

    The public training entrypoint selects a tokenizer by substring matching on
    ``model_name_or_path``.  The pinned local checkpoint directory is otherwise
    correct, but has no model-family name in its path.  A symlink keeps the
    checkpoint bytes unchanged and makes that upstream branch deterministic.
    """
    if "qwen" in str(checkpoint).lower():
        return checkpoint
    compat = checkpoint.parent / f"{checkpoint.name}-qwen-compat"
    if compat.exists() and not compat.is_symlink():
        raise RuntimeError(f"checkpoint compatibility path is not a symlink: {compat}")
    if not compat.exists():
        compat.symlink_to(checkpoint, target_is_directory=True)
    return compat


def _patch_qwen_tokenizer(repo: Path) -> dict[str, str]:
    """Apply the smallest runtime compatibility patch required by Transformers.

    The pinned StreamVLN source calls the Qwen tokenizer with the fast-tokenizer
    default.  With the verified Transformers 4.45.1 environment that returns a
    ``Qwen2TokenizerFast`` without the ``legacy`` attribute used by the public
    dataset preprocessor.  The slow tokenizer exposes the expected API.  This
    edits only the copied public StreamVLN checkout, never GenieSim or the model
    weights, and is idempotent so the final source hash is reproducible.
    """
    path = repo / "streamvln" / "streamvln_train.py"
    original = (
        'tokenizer = transformers.AutoTokenizer.from_pretrained(model_args.model_name_or_path, '
        'cache_dir=training_args.cache_dir, model_max_length=training_args.model_max_length, '
        'padding_side="right")'
    )
    patched = (
        'tokenizer = transformers.AutoTokenizer.from_pretrained(model_args.model_name_or_path, '
        'cache_dir=training_args.cache_dir, model_max_length=training_args.model_max_length, '
        'padding_side="right", use_fast=False)'
    )
    source = path.read_text(encoding="utf-8")
    changed = False
    if patched not in source:
        if original not in source:
            return {"status": "blocked", "path": str(path), "reason": "expected tokenizer call not found"}
        source = source.replace(original, patched, 1)
        changed = True

    vocab_original = "    return model\n\n\ndef train(attn_implementation=None):"
    vocab_patched = (
        "    # Keep the loss reshape aligned with the checkpoint's loaded lm_head.\n"
        "    # The pinned real-world checkpoint loads 151648 output rows while its\n"
        "    # legacy config advertises 152064; Transformers otherwise raises a\n"
        "    # non-divisible view error on the first training batch.\n"
        "    if hasattr(model, \"lm_head\") and hasattr(model.lm_head, \"out_features\"):\n"
        "        model.config.vocab_size = int(model.lm_head.out_features)\n"
        "        model.vocab_size = int(model.lm_head.out_features)\n"
        "    return model\n\n\ndef train(attn_implementation=None):"
    )
    if vocab_patched not in source:
        if vocab_original not in source:
            return {"status": "blocked", "path": str(path), "reason": "expected model return marker not found"}
        source = source.replace(vocab_original, vocab_patched, 1)
        changed = True

    dataset_path = repo / "streamvln" / "dataset" / "vln_action_dataset.py"
    dataset_source = dataset_path.read_text(encoding="utf-8")
    dataset_original = "if i != 0 and not tokenizer.legacy and IS_TOKENIZER_GREATER_THAN_0_14:"
    dataset_patched = "if i != 0 and not getattr(tokenizer, \"legacy\", False) and IS_TOKENIZER_GREATER_THAN_0_14:"
    if dataset_patched not in dataset_source:
        if dataset_original not in dataset_source:
            return {"status": "blocked", "path": str(dataset_path), "reason": "expected tokenizer legacy check not found"}
        dataset_path.write_text(dataset_source.replace(dataset_original, dataset_patched, 1), encoding="utf-8")
        changed = True
    vision_marker = "        model.initialize_vision_tokenizer(model_args, tokenizer=tokenizer)\n"
    vision_patch = (
        "        model.initialize_vision_tokenizer(model_args, tokenizer=tokenizer)\n"
        "        # initialize_vision_tokenizer may resize lm_head for the image token.\n"
        "        if hasattr(model, \"lm_head\") and hasattr(model.lm_head, \"out_features\"):\n"
        "            model.config.vocab_size = int(model.lm_head.out_features)\n"
        "            model.vocab_size = int(model.lm_head.out_features)\n"
    )
    if vision_patch not in source:
        if vision_marker not in source:
            return {"status": "blocked", "path": str(path), "reason": "vision tokenizer marker not found"}
        source = source.replace(vision_marker, vision_patch, 1)
        changed = True
    if changed:
        path.write_text(source, encoding="utf-8")
    return {"status": "applied" if changed else "already_applied", "path": str(path), "dataset_path": str(dataset_path), "vocab_alignment": "lm_head.out_features"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--vision", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    repo = args.repo.expanduser().resolve()
    # Do not call Path.resolve() here: the compatibility symlink intentionally
    # carries the model-family name consumed by the upstream script.
    checkpoint = Path(os.path.abspath(str(args.checkpoint.expanduser())))
    vision = args.vision.expanduser().resolve()
    dataset = args.dataset.expanduser().resolve()
    output = args.output.expanduser().resolve()
    result_path = args.result.expanduser().resolve()

    gates: dict[str, Any] = {}
    gates["streamvln_compat"] = _patch_qwen_tokenizer(repo)
    try:
        gates["dataset_only"] = validate_dataset(
            dataset,
            annotation_path=dataset / "annotations.json",
            verify_image_bytes=True,
            strict=True,
        )
    except Exception as exc:
        gates["dataset_only"] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}

    required_model_files = [checkpoint / "config.json", checkpoint / "model.safetensors.index.json", vision / "config.json"]
    gates["checkpoint_files"] = {
        "status": "ready" if all(path.is_file() for path in required_model_files) else "blocked",
        "files": {str(path): path.is_file() for path in required_model_files},
    }
    checkpoint_for_command = _qwen_compat_checkpoint(checkpoint)
    command = build_command(
        python=args.python,
        repo=repo,
        checkpoint=checkpoint_for_command,
        vision=vision,
        data=dataset,
        output=output,
    )
    command_path = result_path.with_name("train-command.txt")
    command_path.parent.mkdir(parents=True, exist_ok=True)
    command_path.write_text(
        f"PYTHONPATH={repo}:{repo / 'streamvln'} HF_ENDPOINT=https://hf-mirror.com "
        + " ".join(command)
        + "\n",
        encoding="utf-8",
    )
    gates["single_batch_forward_backward"] = {"status": "not_run"}
    gates["full_training"] = {"status": "not_run"}
    gates["adapter_reload"] = {"status": "not_run"}
    if args.execute and gates["dataset_only"].get("invalid", 1) == 0 and gates["checkpoint_files"]["status"] == "ready" and gates["streamvln_compat"]["status"] in {"applied", "already_applied"}:
        output.mkdir(parents=True, exist_ok=True)
        environment = dict(__import__("os").environ)
        environment["PYTHONPATH"] = f"{repo}:{repo / 'streamvln'}"
        environment.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        process = subprocess.run(command, cwd=repo, env=environment, text=True, capture_output=True)
        (result_path.with_name("train.stdout.log")).write_text(process.stdout, encoding="utf-8")
        (result_path.with_name("train.stderr.log")).write_text(process.stderr, encoding="utf-8")
        error = _last_error(process.stderr)
        gates["full_training"] = {"status": "passed" if process.returncode == 0 else "failed", "exit_code": process.returncode}
        if error:
            gates["full_training"]["error"] = error
            if process.returncode != 0 and ("trainer.train" in process.stderr or "0%|" in process.stderr):
                gates["single_batch_forward_backward"] = {
                    "status": "failed",
                    "observed_in": "full_training_first_batch",
                    "error": error,
                }
        adapter_files = sorted(output.glob("adapter_model*"))
        if process.returncode == 0 and adapter_files:
            reload_command = [
                args.python,
                str(Path(__file__).with_name("reload_adapter.py")),
                "--repo", str(repo),
                "--adapter", str(output),
            ]
            reload_env = dict(environment)
            reload_process = subprocess.run(
                reload_command,
                cwd=repo,
                env=reload_env,
                text=True,
                capture_output=True,
            )
            reload_log = result_path.with_name("adapter-reload.log")
            reload_log.write_text(reload_process.stdout + reload_process.stderr, encoding="utf-8")
            gates["adapter_reload"] = {
                "status": "passed" if reload_process.returncode == 0 else "failed",
                "exit_code": reload_process.returncode,
                "command": reload_command,
                "log": str(reload_log),
                "adapter_sha256": {str(path): _sha256(path) for path in adapter_files},
            }
            reload_error = _last_error(reload_process.stderr)
            if reload_error:
                gates["adapter_reload"]["error"] = reload_error
    else:
        gates["full_training"] = {
            "status": "blocked",
            "reason": "checkpoint, strict dataset, or StreamVLN compatibility gate is not ready; no training command was executed",
        }

    result = {
        "schema_version": "geniesim-streamvln/v1",
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "official": False,
        "config": {"lora_r": 8, "lora_alpha": 16, "lora_dropout": 0.05, "epochs": 1, "batch": 1, "learning_rate": 2e-5, "bf16": True, "gradient_checkpointing": True, "mm_tunable_parts": "mm_lora_layer"},
        "gates": gates,
        "command_file": str(command_path),
    }
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"result": str(result_path), "full_training": gates["full_training"]["status"]}))


if __name__ == "__main__":
    main()
