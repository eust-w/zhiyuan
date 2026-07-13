"""Load a trained StreamVLN LoRA adapter in a fresh Python process.

This is deliberately a small, explicit gate for Stage 2.  It loads the same
base ``StreamVLNForCausalLM`` class used by the pinned training entrypoint and
then attaches the adapter with PEFT.  It does not run inference or publish any
weights.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    args = parser.parse_args()

    repo = args.repo.expanduser().resolve()
    adapter = args.adapter.expanduser().resolve()
    config_path = adapter / "adapter_config.json"
    if not config_path.is_file():
        raise FileNotFoundError(config_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    base_name = config.get("base_model_name_or_path")
    if not base_name:
        raise ValueError("adapter_config.json has no base_model_name_or_path")
    base = Path(base_name)
    if not base.exists():
        raise FileNotFoundError(f"base model from adapter config does not exist: {base}")
    if not any((adapter / name).is_file() for name in ("adapter_model.bin", "adapter_model.safetensors")):
        raise FileNotFoundError(f"adapter weights missing in {adapter}")

    sys.path.insert(0, str(repo))
    import torch
    from peft import PeftModel
    from transformers import AutoConfig
    from streamvln.model.stream_video_vln import StreamVLNForCausalLM

    # Match the non-default fields that the pinned training command passes to
    # ``get_model``.  Supplying the Llava config explicitly avoids the
    # Transformers 4.45.1 decoder-config conversion issue on this checkpoint.
    model_config = AutoConfig.from_pretrained(str(base))
    model_config.num_future_steps = 4
    model_config.num_history = 8
    model_config.mm_tunable_parts = "mm_lora_layer"
    model_config.mm_newline_position = "grid"
    model_config.mm_patch_merge_type = "flat"
    model = StreamVLNForCausalLM.from_pretrained(
        str(base),
        config=model_config,
        attn_implementation="sdpa",
        torch_dtype=torch.bfloat16,
        low_cpu_mem_usage=False,
    )
    # The checkpoint's legacy config advertises 152064 rows while the loaded
    # lm_head has 151648 rows; keep Transformers' loss/view metadata coherent.
    if hasattr(model, "lm_head") and hasattr(model.lm_head, "out_features"):
        model.config.vocab_size = int(model.lm_head.out_features)
        model.vocab_size = int(model.lm_head.out_features)
    model = PeftModel.from_pretrained(model, str(adapter), is_trainable=False)
    model.eval()
    trainable = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    print(json.dumps({
        "status": "passed",
        "adapter": str(adapter),
        "base_model": str(base),
        "peft_type": config.get("peft_type"),
        "lora_r": config.get("r"),
        "trainable_parameters": trainable,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
