"""Prepare and optionally execute the official StreamVLN LoRA command.

This wrapper makes the four required gates explicit: dataset-only, one-batch
forward/backward, full training, and adapter reload.  It never fabricates an
adapter when a dependency or checkpoint is missing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .dataset import validate_dataset
from .model_security import validate_model_directory, validate_training_vision_reference


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
        # `qwen` is not a key in StreamVLN's bundled conv_templates. Passing it
        # silently falls back to vicuna_v1 and masks every navigation label.
        "--version", "qwen_2",
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


def checkpoint_safety_gate(checkpoint: Path, vision: Path) -> dict[str, Any]:
    """Validate weights without importing or executing the external checkout."""
    try:
        base_files = validate_model_directory(checkpoint)
        vision_files = validate_model_directory(vision)
        validate_training_vision_reference(checkpoint, vision)
    except (ValueError, OSError) as exc:
        return {"status": "blocked", "error": str(exc), "policy": "local_safetensors_only"}
    return {
        "status": "ready",
        "policy": "local_safetensors_only",
        "files": {str(path): True for path in base_files + vision_files},
        "external_loader_review_required": True,
    }


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
    if compat.exists() or compat.is_symlink():
        if not compat.is_symlink() or compat.resolve() != checkpoint.resolve():
            raise RuntimeError(f"checkpoint compatibility alias points elsewhere: {compat}")
    else:
        compat.symlink_to(checkpoint, target_is_directory=True)
    return compat


def _patch_qwen_tokenizer(repo: Path) -> dict[str, str]:
    # Licensing: the original wrapper is MIT; upstream matching/adapted source
    # fragments retain their applicable Apache-2.0 / CC-BY-NC-SA-4.0 terms.
    # Sources: StreamVLN e48f6ff7e9201d93aae003e8f64b04c00cec13bc,
    # streamvln/streamvln_train.py and streamvln/dataset/vln_action_dataset.py.
    # See the repository-root THIRD_PARTY_NOTICES.md for attribution and changes.
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
    special_ids_original = "    im_start, im_end = tokenizer.additional_special_tokens_ids"
    special_ids_patched = (
        '    im_start = tokenizer.convert_tokens_to_ids("<|im_start|>")\n'
        '    im_end = tokenizer.convert_tokens_to_ids("<|im_end|>")'
    )
    for source_name, current_source in (("training", source), ("dataset", dataset_source)):
        if special_ids_patched not in current_source:
            if special_ids_original not in current_source:
                target_path = path if source_name == "training" else dataset_path
                return {"status": "blocked", "path": str(target_path), "reason": "expected Qwen special-token unpack not found"}
            current_source = current_source.replace(special_ids_original, special_ids_patched, 1)
            changed = True
        if source_name == "training":
            source = current_source
        else:
            dataset_source = current_source
    dataset_original = "if i != 0 and not tokenizer.legacy and IS_TOKENIZER_GREATER_THAN_0_14:"
    dataset_patched = "if i != 0 and not getattr(tokenizer, \"legacy\", False) and IS_TOKENIZER_GREATER_THAN_0_14:"
    if dataset_patched not in dataset_source:
        if dataset_original not in dataset_source:
            return {"status": "blocked", "path": str(dataset_path), "reason": "expected tokenizer legacy check not found"}
        dataset_source = dataset_source.replace(dataset_original, dataset_patched, 1)
        changed = True
    dispatch_original = (
        "    if conversation_lib.default_conversation.sep_style == conversation_lib.SeparatorStyle.PLAIN:\n"
        "        return preprocess_plain(sources, tokenizer)\n"
        "    if conversation_lib.default_conversation.sep_style == conversation_lib.SeparatorStyle.LLAMA_2:\n"
        "        return preprocess_llama_2(sources, tokenizer, has_image=has_image)"
    )
    qwen_dispatch_guard = (
        "    if conversation_lib.default_conversation.version == \"qwen\":\n"
        "        return preprocess_qwen(sources, tokenizer, has_image=has_image)\n"
    )
    plain_dispatch = "    if conversation_lib.default_conversation.sep_style == conversation_lib.SeparatorStyle.PLAIN:\n"
    search_from = 0
    found_dispatch = False
    while True:
        position = dataset_source.find(plain_dispatch, search_from)
        if position < 0:
            break
        found_dispatch = True
        if dataset_source[max(0, position - len(qwen_dispatch_guard)) : position] != qwen_dispatch_guard:
            dataset_source = dataset_source[:position] + qwen_dispatch_guard + dataset_source[position:]
            position += len(qwen_dispatch_guard)
            changed = True
        search_from = position + len(plain_dispatch)
    if not found_dispatch or dispatch_original not in dataset_source:
        return {"status": "blocked", "path": str(dataset_path), "reason": "expected preprocess dispatcher not found"}
    dataset_path.write_text(dataset_source, encoding="utf-8")
    source_search_from = 0
    source_found_dispatch = False
    while True:
        position = source.find(plain_dispatch, source_search_from)
        if position < 0:
            break
        source_found_dispatch = True
        if source[max(0, position - len(qwen_dispatch_guard)) : position] != qwen_dispatch_guard:
            source = source[:position] + qwen_dispatch_guard + source[position:]
            position += len(qwen_dispatch_guard)
            changed = True
        source_search_from = position + len(plain_dispatch)
    if not source_found_dispatch:
        return {"status": "blocked", "path": str(path), "reason": "expected training preprocess dispatcher not found"}
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
    parser.add_argument("--max-steps", type=int, default=None, help="set to 1 for the isolated single-batch gate")
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
    gates["checkpoint_files"] = checkpoint_safety_gate(checkpoint, vision)
    if gates["checkpoint_files"]["status"] == "ready":
        gates["streamvln_compat"] = _patch_qwen_tokenizer(repo)
    else:
        gates["streamvln_compat"] = {"status": "blocked", "reason": "local safetensors preflight failed"}
    try:
        gates["dataset_only"] = validate_dataset(
            dataset,
            annotation_path=dataset / "annotations.json",
            verify_image_bytes=True,
            strict=True,
        )
    except Exception as exc:
        gates["dataset_only"] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}

    checkpoint_for_command = _qwen_compat_checkpoint(checkpoint) if gates["checkpoint_files"]["status"] == "ready" else checkpoint
    command = build_command(
        python=args.python,
        repo=repo,
        checkpoint=checkpoint_for_command,
        vision=vision,
        data=dataset,
        output=output,
        max_steps=args.max_steps,
    )
    command_path = result_path.with_name("train-command.txt")
    command_path.parent.mkdir(parents=True, exist_ok=True)
    command_path.write_text(
        f"PYTHONPATH={repo}:{repo / 'streamvln'} HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "
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
        environment["HF_HUB_OFFLINE"] = "1"
        environment["TRANSFORMERS_OFFLINE"] = "1"
        stdout_path = result_path.with_name("train.stdout.log")
        stderr_path = result_path.with_name("train.stderr.log")
        peak_gpu_memory_mib = 0
        with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open("w", encoding="utf-8") as stderr_handle:
            process = subprocess.Popen(command, cwd=repo, env=environment, text=True, stdout=stdout_handle, stderr=stderr_handle)
            while process.poll() is None:
                memory = subprocess.run(
                    ["nvidia-smi", "--query-compute-apps=used_memory", "--format=csv,noheader,nounits"],
                    text=True,
                    capture_output=True,
                )
                if memory.returncode == 0:
                    values = [int(value.strip()) for value in memory.stdout.splitlines() if value.strip().isdigit()]
                    peak_gpu_memory_mib = max(peak_gpu_memory_mib, sum(values))
                time.sleep(0.5)
            return_code = process.wait()
        stdout_text = stdout_path.read_text(encoding="utf-8")
        stderr_text = stderr_path.read_text(encoding="utf-8")
        losses = [float(value) for value in re.findall(r"'loss':\s*([0-9.eE+-]+)", stdout_text)]
        grad_norms = [float(value) for value in re.findall(r"'grad_norm':\s*([0-9.eE+-]+)", stdout_text)]
        finite_nonzero_update = any(math.isfinite(value) and value > 0 for value in losses) and any(
            math.isfinite(value) and value > 0 for value in grad_norms
        )
        training_status = "passed" if return_code == 0 and finite_nonzero_update else "failed"
        training_record = {
            "status": training_status,
            "exit_code": return_code,
            "observed_steps": len(losses),
            "loss_first": losses[0] if losses else None,
            "loss_last": losses[-1] if losses else None,
            "grad_norm_max": max(grad_norms) if grad_norms else None,
            "peak_gpu_memory_mib": peak_gpu_memory_mib,
            "nan_or_inf": any(not math.isfinite(value) for value in losses + grad_norms),
        }
        if return_code == 0 and not finite_nonzero_update:
            training_record["error"] = "no finite non-zero loss/gradient update; labels may be fully masked"
        error = _last_error(stderr_text)
        if error:
            training_record["error"] = error
        if args.max_steps == 1:
            gates["single_batch_forward_backward"] = training_record
            gates["full_training"] = {"status": "not_run", "reason": "single-batch gate invocation"}
        else:
            gates["single_batch_forward_backward"] = {
                "status": "passed" if training_status == "passed" else "failed",
                "observed_in": "full_training_first_batch",
                "loss": losses[0] if losses else None,
                "grad_norm": grad_norms[0] if grad_norms else None,
            }
            gates["full_training"] = training_record
        adapter_files = sorted(output.glob("adapter_model*"))
        if args.max_steps is None and training_status == "passed" and adapter_files:
            reload_command = [
                args.python,
                str(Path(__file__).with_name("reload_adapter.py")),
                "--repo", str(repo),
                "--adapter", str(output),
                "--vision", str(vision),
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
