"""Load a trained StreamVLN LoRA adapter in a fresh Python process.

This is deliberately a small, explicit gate for Stage 2.  It loads the same
base ``StreamVLNForCausalLM`` class used by the pinned training entrypoint and
then attaches the adapter with PEFT.  It does not run inference or publish any
weights.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from .model_security import resolve_vision_directory, validate_adapter_directory, validate_model_directory, vision_model_name
    from .streamvln_compat import prepare_checkout
except ImportError:  # Direct script invocation by stage2_preflight.
    from model_security import resolve_vision_directory, validate_adapter_directory, validate_model_directory, vision_model_name
    from streamvln_compat import prepare_checkout


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--vision", type=Path, help="local safetensors vision tower override")
    args = parser.parse_args()

    repo = args.repo.expanduser().resolve()
    adapter = args.adapter.expanduser().resolve()
    config = validate_adapter_directory(adapter)
    base_name = config.get("base_model_name_or_path")
    if not base_name:
        raise ValueError("adapter_config.json has no base_model_name_or_path")
    if not isinstance(base_name, str):
        raise ValueError("base_model_name_or_path must be a local directory string")
    base = Path(base_name).expanduser().resolve()
    validate_model_directory(base)
    vision = resolve_vision_directory(base, args.vision)
    vision_name = vision_model_name(vision)
    compatibility = prepare_checkout(repo)

    # Set these before importing Hugging Face or caller-supplied StreamVLN.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    sys.path.insert(0, str(repo))
    import torch
    from peft import PeftModel
    from llava.model.language_model.llava_qwen import load_streamvln_config, restore_streamvln_vision_weights
    from streamvln.model.stream_video_vln import StreamVLNForCausalLM

    # Match the non-default fields that the pinned training command passes to
    # ``get_model``. Read top-level Qwen dimensions explicitly instead of
    # dispatching the checkpoint's legacy "llava" type to a Llama decoder.
    model_config = load_streamvln_config(base)
    model_config.mm_vision_tower = vision_name
    model_config.vision_tower = vision_name
    model_config.num_future_steps = 4
    model_config.num_history = 8
    model_config.mm_tunable_parts = "mm_lora_layer"
    model_config.mm_newline_position = "grid"
    model_config.mm_patch_merge_type = "flat"
    model = StreamVLNForCausalLM.from_pretrained(
        str(base),
        config=model_config,
        attn_implementation="sdpa",
        dtype=torch.bfloat16,
        use_safetensors=True,
        local_files_only=True,
        trust_remote_code=False,
    )
    # Match loss metadata to the actual loaded head without slicing checkpoint
    # weights. A subsequent tokenizer resize is a separate operation.
    if hasattr(model, "lm_head") and hasattr(model.lm_head, "out_features"):
        model.config.vocab_size = int(model.lm_head.out_features)
        model.vocab_size = int(model.lm_head.out_features)
    # The guard rejects PEFT's alternate pickle filename before this load.
    model = PeftModel.from_pretrained(model, str(adapter), is_trainable=False, local_files_only=True)
    # Materialize the tower only after PEFT selects the language projections;
    # the helper restores and validates the base checkpoint's complete tower.
    vision_weights = restore_streamvln_vision_weights(model, base)
    model.eval()
    trainable = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    print(json.dumps({
        "status": "passed",
        "adapter": str(adapter),
        "base_model": str(base),
        "peft_type": config.get("peft_type"),
        "lora_r": config.get("r"),
        "trainable_parameters": trainable,
        "compatibility": compatibility,
        "vision_weights": vision_weights,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
