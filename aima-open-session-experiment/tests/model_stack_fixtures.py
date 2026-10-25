"""Real, small, local-only fixtures for the dedicated model migration gate.

No published checkpoint is downloaded. These fixtures instantiate the actual
StreamVLN classes and save randomly initialized safetensors in a temporary tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


def activate_upstream() -> Path:
    location = os.environ.get("STREAMVLN_REPO")
    if not location:
        raise RuntimeError("Set STREAMVLN_REPO to the pinned upstream checkout for this dedicated test gate")
    root = Path(location).resolve(strict=True)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    from adapter.streamvln_compat import prepare_checkout

    prepare_checkout(root)
    sys.path[:0] = [str(root), str(root / "streamvln")]
    import torch

    torch.set_num_threads(1)
    torch.manual_seed(371)
    return root


def create_vision(root: Path, *, image_size: int = 16, patch_size: int = 4) -> Path:
    from llava.model.multimodal_encoder.siglip_encoder import SigLipVisionConfig, SigLipVisionModel

    location = root / "tiny-siglip"
    config = SigLipVisionConfig(
        hidden_size=16,
        intermediate_size=32,
        num_hidden_layers=2,
        num_attention_heads=4,
        image_size=image_size,
        patch_size=patch_size,
        attention_dropout=0.0,
    )
    model = SigLipVisionModel(config)
    model.save_pretrained(location, safe_serialization=True)
    return location


def create_tokenizer(root: Path):
    from tokenizers import Tokenizer, models, pre_tokenizers
    from transformers import PreTrainedTokenizerFast

    words = [
        "[UNK]", "[PAD]", "[EOS]", "<|im_start|>", "<|im_end|>",
        "<image>", "<memory>", "user_only_marker", "assistant_only_marker",
        "system", "user", "assistant", "go", "forward", "stop", "left", "right",
        "You", "are", "a", "helpful", "assistant", ".", "red", "target",
        "↑", "←", "→", "STOP",
    ]
    words = list(dict.fromkeys(words))
    backend = Tokenizer(models.WordLevel({word: i for i, word in enumerate(words)}, unk_token="[UNK]"))
    backend.pre_tokenizer = pre_tokenizers.Whitespace()
    tokenizer = PreTrainedTokenizerFast(
        tokenizer_object=backend,
        unk_token="[UNK]",
        pad_token="[PAD]",
        eos_token="[EOS]",
        additional_special_tokens=["<|im_start|>", "<|im_end|>", "<image>", "<memory>"],
        model_max_length=256,
    )
    tokenizer.chat_template = (
        "{% for message in messages %}{{'<|im_start|>' + message['role'] + '\\n' + "
        "message['content'] + '<|im_end|>' + '\\n'}}{% endfor %}"
    )
    tokenizer.save_pretrained(root / "tiny-tokenizer")
    return tokenizer


def create_model(vision: Path):
    from llava.model.language_model.llava_qwen import LlavaQwenConfig
    from streamvln.model.stream_video_vln import StreamVLNForCausalLM

    config = LlavaQwenConfig(
        vocab_size=64,
        hidden_size=32,
        intermediate_size=64,
        num_hidden_layers=2,
        num_attention_heads=4,
        num_key_value_heads=2,
        max_position_embeddings=256,
        bos_token_id=1,
        eos_token_id=2,
        pad_token_id=1,
        attention_dropout=0.0,
        tie_word_embeddings=False,
        mm_vision_tower=str(vision),
        mm_hidden_size=16,
        mm_projector_type="linear",
        mm_patch_merge_type="flat",
        mm_spatial_pool_mode="average",
        mm_vision_select_layer=-1,
        mm_vision_select_feature="patch",
        mm_tunable_parts="mm_lora_layer",
        num_history=1,
        tokenizer_model_max_length=256,
        tokenizer_padding_side="right",
        use_cache=False,
    )
    config._attn_implementation = "eager"
    model = StreamVLNForCausalLM(config)
    model.get_vision_tower().load_model()
    assert_position_ids(model.get_vision_tower().vision_tower)
    return model.to(device="cpu", dtype=__import__("torch").float32)


def assert_position_ids(vision_model) -> None:
    import torch

    embeddings = vision_model.vision_model.embeddings
    expected = torch.arange(
        embeddings.num_positions, dtype=torch.long, device=embeddings.position_embedding.weight.device,
    ).unsqueeze(0)
    torch.testing.assert_close(embeddings.position_ids, expected, rtol=0, atol=0)
    assert "position_ids" not in embeddings.state_dict()


def load_model(location: Path, *, load_vision: bool = True):
    import torch
    from llava.model.language_model.llava_qwen import load_streamvln_config, restore_streamvln_vision_weights
    from streamvln.model.stream_video_vln import StreamVLNForCausalLM

    model = StreamVLNForCausalLM.from_pretrained(
        location,
        config=load_streamvln_config(location),
        local_files_only=True,
        trust_remote_code=False,
        use_safetensors=True,
        dtype=torch.float32,
        attn_implementation="eager",
    )
    if load_vision:
        restore_streamvln_vision_weights(model, location)
        assert_position_ids(model.get_vision_tower().vision_tower)
    return model.cpu()


def batch(*, history: bool = False, offset: int = 0):
    import torch
    from streamvln.utils.utils import IMAGE_TOKEN_INDEX, MEMORY_TOKEN_INDEX, IGNORE_INDEX

    if history:
        tokens = [7, MEMORY_TOKEN_INDEX, 8, IMAGE_TOKEN_INDEX, 9, 10]
        times = [[1, 2]]
    else:
        tokens = [7, IMAGE_TOKEN_INDEX, 8, IMAGE_TOKEN_INDEX, 9, 10]
        times = [[0, 1]]
    ids = torch.tensor([tokens])
    labels = ids.clone()
    labels[:, :-2] = IGNORE_INDEX
    generator = torch.Generator().manual_seed(107 + offset)
    return {
        "input_ids": ids,
        "labels": labels,
        "attention_mask": torch.ones_like(ids),
        "images": torch.rand((1, 2, 3, 16, 16), generator=generator),
        "time_ids": times,
        "task_type": [0],
    }


def adapter_digest(model) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(model.named_parameters()):
        if "lora_" in name:
            digest.update(name.encode())
            digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def collate_rows(rows):
    import torch

    return {
        key: torch.cat([row[key] for row in rows], dim=0)
        if isinstance(rows[0][key], torch.Tensor)
        else sum([row[key] for row in rows], [])
        for key in rows[0]
    }


def generate_once(model):
    data = batch()
    model.reset(1)
    return model.generate(
        inputs=data["input_ids"], images=data["images"], time_ids=data["time_ids"],
        task_type=data["task_type"], env_id=0, do_sample=False,
        min_new_tokens=3, max_new_tokens=3, use_cache=True,
        return_dict_in_generate=True,
    ).sequences


def create_cli_training_case(root: Path):
    from PIL import Image

    # Keep the upstream dataset's real 384px processor while reducing its patch
    # grid to 4x4. This remains the actual SigLIP implementation, not a stub.
    vision = create_vision(root / "cli-assets", image_size=384, patch_size=96)
    base = root / "tiny-qwen-cli"
    model = create_model(vision)
    import torch

    with torch.no_grad():
        model.get_vision_tower().vision_tower.vision_model.embeddings.patch_embedding.weight[0].add_(1.0)
    model.save_pretrained(base, safe_serialization=True)
    tokenizer = create_tokenizer(root)
    tokenizer.save_pretrained(base)
    legacy_config = json.loads((base / "config.json").read_text(encoding="utf-8"))
    legacy_config["model_type"] = "llava"
    legacy_config["architectures"] = ["StreamVLNForCausalLM"]
    legacy_config.pop("pad_token_id", None)
    legacy_config.pop("rope_parameters", None)
    legacy_config["rope_theta"] = 1000000.0
    legacy_config["rope_scaling"] = None
    legacy_config["text_config"] = {
        "model_type": "llama", "vocab_size": 32000, "hidden_size": 4096,
        "intermediate_size": 11008, "num_hidden_layers": 32,
        "num_attention_heads": 32, "num_key_value_heads": 32,
        "max_position_embeddings": 2048,
    }
    (base / "config.json").write_text(json.dumps(legacy_config), encoding="utf-8")
    dataset = root / "dataset"
    rgb = dataset / "episode-1" / "rgb"
    rgb.mkdir(parents=True)
    for index in range(4):
        Image.new("RGB", (32, 32), color=(40 * index, 30, 100)).save(rgb / f"{index:06d}.png")
    (dataset / "annotations.json").write_text(json.dumps([{
        "video": "episode-1", "instructions": ["go red target"], "actions": [-1, 1, 2, 3],
    }]), encoding="utf-8")
    return base, vision, dataset


def write_sharded_checkpoint(location: Path, tensors):
    from safetensors.torch import save_file

    location.mkdir(parents=True, exist_ok=True)
    vision = {name: tensor for name, tensor in tensors.items() if name.startswith("model.vision_tower.")}
    language = {name: tensor for name, tensor in tensors.items() if name not in vision}
    save_file(vision, location / "vision.safetensors")
    save_file(language, location / "language.safetensors")
    index = {
        "metadata": {"total_size": sum(tensor.numel() * tensor.element_size() for tensor in tensors.values())},
        "weight_map": {
            name: "vision.safetensors" if name in vision else "language.safetensors" for name in tensors
        },
    }
    (location / "model.safetensors.index.json").write_text(json.dumps(index), encoding="utf-8")
    monolithic = location / "model.safetensors"
    if monolithic.exists():
        monolithic.unlink()
    return index


def reload_in_fresh_process(root: Path) -> None:
    activate_upstream()
    import torch
    from peft import PeftModel
    from safetensors.torch import load_file
    from llava.model.language_model.llava_qwen import restore_streamvln_vision_weights

    torch.use_deterministic_algorithms(True)
    torch.utils.deterministic.fill_uninitialized_memory = True
    model = PeftModel.from_pretrained(
        load_model(root / "base", load_vision=False), root / "adapter", local_files_only=True,
    )
    restore_streamvln_vision_weights(model, root / "base")
    assert_position_ids(model.get_vision_tower().vision_tower)
    assert not any("lora_" in name for name, _ in model.get_vision_tower().named_parameters())
    model.eval()
    with torch.no_grad():
        actual = model(**batch()).logits
    expected = load_file(root / "expected.safetensors")
    torch.testing.assert_close(actual, expected["logits"], rtol=1e-5, atol=1e-6)
    torch.testing.assert_close(generate_once(model), expected["sequences"], rtol=0, atol=0)
    print(json.dumps({"adapter_digest": adapter_digest(model), "shape": list(actual.shape), "device": str(actual.device)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reload", type=Path, required=True)
    args = parser.parse_args()
    reload_in_fresh_process(args.reload)
