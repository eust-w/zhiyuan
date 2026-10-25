"""Run StreamVLN base/LoRA actions through the live GenieSim adapter.

This evaluator deliberately does not reuse the deterministic A* controller.
For every held-out episode it resets the loopback GenieSim service, feeds the
returned RGB/depth/pose observation to the pinned StreamVLN model, decodes the
model's action tokens, sends those actions back to GenieSim, and computes
metrics from the resulting trajectory.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import numpy as np
from PIL import Image

try:
    from .metrics import summarize_episode, summarize_runs
    from .model_security import resolve_vision_directory, validate_adapter_directory, validate_model_directory, vision_model_name
    from .streamvln_compat import prepare_checkout
except ImportError:  # pragma: no cover - direct script execution on GPUFree
    from adapter.metrics import summarize_episode, summarize_runs
    from adapter.model_security import resolve_vision_directory, validate_adapter_directory, validate_model_directory, vision_model_name
    from adapter.streamvln_compat import prepare_checkout


def request_json(base_url: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        base_url.rstrip("/") + path,
        data=body,
        method="GET" if payload is None else "POST",
        headers={} if payload is None else {"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"adapter request failed: {path}: {exc}") from exc
    if not isinstance(result, dict):
        raise RuntimeError(f"adapter returned a non-object for {path}")
    if "error" in result:
        raise RuntimeError(f"adapter error for {path}: {result['error']}")
    return result


def pose_xy(observation: dict[str, Any]) -> tuple[float, float]:
    matrix = observation.get("pose_matrix")
    if not isinstance(matrix, list) or len(matrix) != 16:
        raise ValueError("observation has no 4x4 pose_matrix")
    return float(matrix[3]), float(matrix[7])


def path_length(observations: list[dict[str, Any]]) -> float:
    return sum(math.dist(pose_xy(a), pose_xy(b)) for a, b in zip(observations, observations[1:]))


class StreamVLNRunner:
    """Load one model variant and expose deterministic RGB-D generation."""

    def __init__(self, *, repo: Path, root: Path, base: Path, vision: Path, adapter: Path | None, max_length: int, decoder: str = "generate"):
        validate_model_directory(base)
        vision = resolve_vision_directory(base, vision)
        if adapter is not None:
            validate_adapter_directory(adapter)
        vision_name = vision_model_name(vision)
        self.compatibility = prepare_checkout(repo)
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        sys.path.insert(0, str(repo))
        sys.path.insert(0, str(repo / "streamvln"))
        import torch
        from peft import PeftModel
        from transformers import AutoTokenizer
        from llava.model.language_model.llava_qwen import load_streamvln_config, restore_streamvln_vision_weights
        import streamvln.model.stream_video_vln as stream_video_vln
        from streamvln.model.stream_video_vln import StreamVLNForCausalLM
        from streamvln.utils.utils import (
            DEFAULT_IMAGE_TOKEN,
            DEFAULT_MEMORY_TOKEN,
            IMAGE_TOKEN_INDEX,
            MEMORY_TOKEN_INDEX,
        )

        self.torch = torch
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if self.device.type != "cuda":
            raise RuntimeError("StreamVLN model evaluation requires CUDA; refusing CPU fallback")

        print(json.dumps({"event": "model_load_start", "base": str(base), "vision": vision_name, "adapter": str(adapter) if adapter else None}), flush=True)
        # Legacy checkpoint metadata says "llava" but its top-level fields
        # describe Qwen. Avoid AutoConfig constructing a default Llama decoder.
        config = load_streamvln_config(base)
        config.num_future_steps = 4
        config.num_history = 8
        config.mm_tunable_parts = "mm_lora_layer"
        config.mm_newline_position = "grid"
        config.mm_patch_merge_type = "flat"
        config.mm_vision_tower = vision_name
        config.vision_tower = vision_name

        model = StreamVLNForCausalLM.from_pretrained(
            str(base),
            config=config,
            attn_implementation="sdpa",
            dtype=torch.bfloat16,
            use_safetensors=True,
            local_files_only=True,
            trust_remote_code=False,
        )
        # Keep a compact first-call trace while adapting the public checkpoint
        # to the live runner.  This catches duplicate ``utils`` imports and
        # special-token drift before a CUDA kernel can obscure the cause.
        original_prepare = model.prepare_inputs_labels_for_multimodal
        prepare_calls = {"count": 0}
        def traced_prepare(*prepare_args, **prepare_kwargs):
            prepare_calls["count"] += 1
            if prepare_calls["count"] <= 2:
                ids = prepare_args[0] if prepare_args else prepare_kwargs.get("input_ids")
                if ids is not None:
                    print(json.dumps({
                        "event": "prepare_trace",
                        "call": prepare_calls["count"],
                        "shape": list(ids.shape),
                        "image_count": int((ids == int(stream_video_vln.IMAGE_TOKEN_INDEX)).sum().item()),
                        "memory_count": int((ids == int(stream_video_vln.MEMORY_TOKEN_INDEX)).sum().item()),
                        "special_values": ids[(ids == int(stream_video_vln.IMAGE_TOKEN_INDEX)) | (ids == int(stream_video_vln.MEMORY_TOKEN_INDEX))].detach().cpu().tolist(),
                        "model_image_index": int(stream_video_vln.IMAGE_TOKEN_INDEX),
                        "model_memory_index": int(stream_video_vln.MEMORY_TOKEN_INDEX),
                    }), flush=True)
            return original_prepare(*prepare_args, **prepare_kwargs)
        model.prepare_inputs_labels_for_multimodal = traced_prepare
        if adapter is not None:
            model = PeftModel.from_pretrained(model, str(adapter), is_trainable=False, local_files_only=True)

        tokenizer = AutoTokenizer.from_pretrained(
            str(base), model_max_length=max_length, padding_side="right",
            local_files_only=True, trust_remote_code=False,
        )
        model_args = SimpleNamespace(
            mm_use_im_patch_token=True,
            mm_use_im_start_end=False,
            tune_mm_mlp_adapter=False,
            pretrain_mm_mlp_adapter=None,
        )
        model.initialize_vision_tokenizer(model_args, tokenizer=tokenizer)
        if hasattr(model, "lm_head") and hasattr(model.lm_head, "out_features"):
            model.config.vocab_size = int(model.lm_head.out_features)
            model.vocab_size = int(model.lm_head.out_features)

        # Attach PEFT before materializing the tower so language-target LoRA
        # does not also wrap vision projections. Then restore the base model's
        # own visual weights rather than silently retaining standalone SigLIP.
        self.vision_weights = restore_streamvln_vision_weights(model, base)
        vision_tower = model.get_vision_tower()
        # PEFT forwards most methods but does not preserve instance-level
        # monkey patches, so install the compatibility shim on the actual
        # StreamVLN base model for both plain and LoRA variants.
        target_model = model.get_base_model() if adapter is not None else model
        original_encode_rgbd = target_model.encode_rgbd
        def compat_encode_rgbd(*encode_args, **encode_kwargs):
            image_features, memory_features = original_encode_rgbd(*encode_args, **encode_kwargs)
            # The public model occasionally asks for a memory token during
            # the first autoregressive decode even though the observation
            # window has only one frame.  Reuse that encoded frame as a
            # one-frame memory feature rather than dereferencing None.  This
            # keeps the model path real and deterministic; later windows use
            # the model's own history features unchanged.
            patched_memory = [
                image_features[index] if memory is None else memory
                for index, memory in enumerate(memory_features)
            ]
            return image_features, patched_memory
        target_model.encode_rgbd = compat_encode_rgbd
        model.requires_grad_(False)
        model.to(self.device)
        model.eval()
        model.reset(1)

        tokenizer = copy.deepcopy(tokenizer)
        tokenizer.add_tokens(["<image>"], special_tokens=True)
        tokenizer.add_tokens(["<memory>"], special_tokens=True)
        tokenizer.chat_template = (
            "{% for message in messages %}{{'<|im_start|>' + message['role'] + '\\n' + "
            "message['content'] + '<|im_end|>' + '\\n'}}{% endfor %}"
        )
        self.model = model
        self.tokenizer = tokenizer
        self.image_processor = vision_tower.image_processor
        self.image_token = DEFAULT_IMAGE_TOKEN
        self.memory_token = DEFAULT_MEMORY_TOKEN
        # Use the exact constants resolved by the model module.  The repo is
        # imported with ``streamvln`` on PYTHONPATH, so importing the same
        # module avoids a duplicate ``utils`` package resolving differently.
        self.image_token_index = int(stream_video_vln.IMAGE_TOKEN_INDEX)
        self.memory_token_index = int(stream_video_vln.MEMORY_TOKEN_INDEX)
        self.variant = "lora" if adapter is not None else "base"
        self.decoder = decoder
        self.repo = repo
        self.root = root
        self._last_input_length = 0
        self._prepare_trace_installed = False
        embed_tokens = model.get_model().embed_tokens
        print(json.dumps({
            "event": "model_load_done",
            "variant": self.variant,
            "device": str(self.device),
            "vocab_size": int(model.lm_head.out_features),
            "embedding_rows": int(embed_tokens.num_embeddings),
            "image_token_index": self.image_token_index,
            "memory_token_index": self.memory_token_index,
            "utils_image_token_index": int(IMAGE_TOKEN_INDEX),
            "utils_memory_token_index": int(MEMORY_TOKEN_INDEX),
            "decoder": self.decoder,
            "vision_weights": self.vision_weights,
        }), flush=True)

    def _prompt_ids(self, instruction: str, step_id: int):
        content = (
            "You are an autonomous navigation assistant. Your task is to follow this instruction: "
            f"{instruction} Use four actions: TURN LEFT (←), TURN RIGHT (→), "
            "MOVE FORWARD (↑) by 25 centimeters, or STOP. "
            f"The current visual observation is {self.image_token}."
        )
        if step_id > 0:
            content += f" Historical observations are available as {self.memory_token}."
        messages = [{"role": "user", "content": content}, {"role": "assistant", "content": ""}]
        ids = self.tokenizer.apply_chat_template(messages, return_tensors="pt", return_dict=False)
        image_id = self.tokenizer.convert_tokens_to_ids(self.image_token)
        memory_id = self.tokenizer.convert_tokens_to_ids(self.memory_token)
        ids[ids == image_id] = self.image_token_index
        ids[ids == memory_id] = self.memory_token_index
        self._last_input_length = int(ids.shape[1])
        return ids.to(self.device)

    def _observation_tensors(self, observation: dict[str, Any]):
        torch = self.torch
        image_path = self.root / str(observation["rgb_path"])
        depth_path = self.root / str(observation["depth_path"])
        image = Image.open(image_path).convert("RGB")
        image_tensor = self.image_processor.preprocess(image, return_tensors="pt")["pixel_values"][0]

        depth = np.load(depth_path, allow_pickle=False).astype(np.float32)
        depth = np.nan_to_num(depth, nan=10.0, posinf=10.0, neginf=0.0)
        depth_mm = np.clip(depth * 1000.0, 0.0, 65535.0).astype(np.uint16)
        depth_image = Image.fromarray(depth_mm, mode="I;16").resize((384, 384), Image.Resampling.NEAREST)
        depth_tensor = torch.from_numpy(np.asarray(depth_image, dtype=np.float32) / 1000.0)

        pose = torch.tensor(observation["pose_matrix"], dtype=torch.float32).reshape(4, 4)
        width, height = image.size
        hfov = math.radians(90.0)
        fx = fy = width / (2.0 * math.tan(hfov / 2.0))
        intrinsic = torch.tensor(
            [[fx, 0.0, (width - 1) / 2.0, 0.0], [0.0, fy, (height - 1) / 2.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]],
            dtype=torch.float32,
        )
        def batch(value: Any) -> Any:
            return value.unsqueeze(0).unsqueeze(0).to(device=self.device, dtype=torch.bfloat16)
        return batch(image_tensor), batch(depth_tensor), batch(pose), batch(intrinsic)

    @staticmethod
    def parse_actions(text: str) -> list[int]:
        # Search only the assistant tail when a full prompt is returned.  The
        # fallback STOP is intentional: invalid model output is safety STOP.
        tail = text.rsplit("assistant\n", 1)[-1]
        patterns: list[tuple[str, int]] = [
            ("TURN LEFT", 2), ("TURN RIGHT", 3), ("MOVE FORWARD", 1),
            ("←", 2), ("→", 3), ("↑", 1), ("STOP", 0),
        ]
        hits: list[tuple[int, int]] = []
        upper = tail.upper()
        for token, action in patterns:
            haystack = upper if token.isalpha() or " " in token else tail
            start = 0
            while True:
                index = haystack.find(token, start)
                if index < 0:
                    break
                hits.append((index, action))
                start = index + len(token)
        hits.sort(key=lambda item: item[0])
        actions: list[int] = []
        for _, action in hits:
            if not actions or actions[-1] != action or action == 0:
                actions.append(action)
        return actions[:4] or [0]

    def predict(self, observation: dict[str, Any], instruction: str, step_id: int) -> dict[str, Any]:
        torch = self.torch
        inputs = self._prompt_ids(instruction, step_id)
        normal_ids = inputs[(inputs != self.image_token_index) & (inputs != self.memory_token_index)]
        embedding_rows = int(self.model.get_model().embed_tokens.num_embeddings)
        image_count = int((inputs == self.image_token_index).sum().item())
        memory_count = int((inputs == self.memory_token_index).sum().item())
        if step_id == 0:
            debug_ids = inputs[0][-80:].detach().clone()
            debug_ids[debug_ids == self.image_token_index] = self.tokenizer.convert_tokens_to_ids(self.image_token)
            debug_ids[debug_ids == self.memory_token_index] = self.tokenizer.convert_tokens_to_ids(self.memory_token)
            print(json.dumps({
                "event": "prompt_tokens",
                "step_id": step_id,
                "image_count": image_count,
                "memory_count": memory_count,
                "shape": list(inputs.shape),
                "tail": self.tokenizer.decode(debug_ids, skip_special_tokens=False),
            }, ensure_ascii=False), flush=True)
        if normal_ids.numel() and (int(normal_ids.min()) < 0 or int(normal_ids.max()) >= embedding_rows):
            raise ValueError(
                f"token id outside embedding range: min={int(normal_ids.min())} max={int(normal_ids.max())} "
                f"embedding_rows={embedding_rows} image_tokens={image_count} memory_tokens={memory_count}"
            )
        images, depths, poses, intrinsics = self._observation_tensors(observation)
        model_inputs = {
            "inputs": inputs,
            "images": images,
            "depths": depths,
            "poses": poses,
            "intrinsics": intrinsics,
            "env_id": 0,
            "time_ids": [[step_id]],
            "task_type": [0],
        }
        if not self._prepare_trace_installed:
            def trace_prepare(frame, event, arg):
                if event == "line" and frame.f_code.co_filename.endswith("stream_video_vln.py") and frame.f_lineno == 224:
                    loc = frame.f_locals
                    print(json.dumps({
                        "event": "prepare_branch_trace",
                        "num_images": int(loc["num_images"]),
                        "num_memories": int(loc["num_memories"]),
                        "special_tokens": [int(x) for x in loc["special_tokens"]],
                        "memory_features_is_none": loc["memory_features"] is None,
                    }), flush=True)
                    self._prepare_trace_installed = True
                    sys.settrace(None)
                    return None
                return trace_prepare
            sys.settrace(trace_prepare)
        start = time.monotonic()
        with torch.inference_mode():
            if self.decoder == "forward":
                outputs = self.model(
                    input_ids=inputs,
                    images=images,
                    depths=depths,
                    poses=poses,
                    intrinsics=intrinsics,
                    env_id=0,
                    time_ids=[[step_id]],
                    task_type=[0],
                    use_cache=False,
                    return_dict=True,
                )
                logits = outputs.logits[:, -1, :]
                top_ids = torch.topk(logits, k=min(16, logits.shape[-1]), dim=-1).indices[0].tolist()
                decoded_parts = [self.tokenizer.decode([int(token_id)], skip_special_tokens=False) for token_id in top_ids]
                decoded = "".join(decoded_parts)
                actions = []
                for part in decoded_parts:
                    parsed = self.parse_actions(part)
                    if parsed:
                        actions = parsed
                        break
                if not actions:
                    actions = [0]
            else:
                outputs = self.model.generate(
                    **model_inputs,
                    do_sample=False,
                    num_beams=1,
                    # The action vocabulary is at most four symbols plus
                    # delimiters; keeping this bounded prevents unbounded KV
                    # growth while preserving the model's action sequence.
                    max_new_tokens=16,
                    use_cache=True,
                    return_dict_in_generate=True,
                )
                decoded = self.tokenizer.batch_decode(outputs.sequences, skip_special_tokens=False)[0]
                actions = self.parse_actions(decoded)
        return {
            "step_id": step_id,
            "decoded": decoded[-2000:],
            "actions": actions,
            "latency_s": time.monotonic() - start,
            "sequence_length": int(outputs.sequences.shape[1]) if hasattr(outputs, "sequences") else int(inputs.shape[1]),
        }

    def reset_episode(self) -> None:
        self.model.reset_for_env(0)
        if self.device.type == "cuda":
            self.torch.cuda.empty_cache()

    def reset_model_window(self) -> None:
        """Drop the StreamVLN KV/image cache at an 8-action boundary."""
        self.model.reset_for_env(0)
        if self.device.type == "cuda":
            self.torch.cuda.empty_cache()


def run_episode(
    *, runner: StreamVLNRunner, base_url: str, root: Path, metadata: dict[str, Any], max_steps: int, run_tag: str
) -> dict[str, Any]:
    source_id = str(metadata["episode_id"])
    episode_id = f"model-{runner.variant}-{run_tag}-{source_id}"
    instruction = str(metadata["instruction"])
    reset = request_json(
        base_url,
        "/v1/episodes/reset",
        {
            "schema_version": "geniesim-streamvln/v1",
            "episode_id": episode_id,
            "seed": int(metadata.get("seed", 0)),
            "instruction": instruction,
            "target_id": str(metadata.get("target_id", "red-target-marker")),
        },
    )
    runner.reset_episode()
    observations = [reset]
    actions: list[int] = []
    events: list[dict[str, Any]] = []
    queued: list[int] = []
    current = reset
    for step_id in range(max_steps):
        if current.get("terminated") or current.get("truncated"):
            break
        if not queued:
            prediction = runner.predict(current, instruction, step_id)
            queued = list(prediction["actions"])
            events.append(prediction)
        action = int(queued.pop(0))
        if action not in (0, 1, 2, 3):
            action = 0
        response = request_json(
            base_url,
            f"/v1/episodes/{episode_id}/step",
            {"request_id": f"{episode_id}-{step_id:04d}", "action_id": action},
        )
        actions.append(action)
        observations.append(response)
        current = response
        if (step_id + 1) % 8 == 0:
            runner.reset_model_window()
        if action == 0 or response.get("terminated") or response.get("truncated"):
            break
    request_json(base_url, f"/v1/episodes/{episode_id}/close", {})
    distances = [float(obs["distance_to_goal_m"]) for obs in observations]
    row = summarize_episode(
        episode_id=source_id,
        distances=distances,
        actions=actions,
        path_length=path_length(observations),
        collisions=sum(1 for obs in observations if obs.get("collision")),
        max_steps=max_steps,
    )
    row.update(
        {
            "source_episode_id": source_id,
            "model_variant": runner.variant,
            "instruction": instruction,
            "seed": int(metadata.get("seed", 0)),
            "adapter_episode_id": episode_id,
            "observations": observations,
            "predictions": events,
        }
    )
    return row


def update_eval_result(path: Path, variant: str, result: dict[str, Any]) -> None:
    if not path.is_file():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    data["metric_source"] = "eval_result.json"
    data["heldout_episode_ids"] = result["episode_ids"]
    data[f"{variant}_model"] = {
        "status": "passed",
        "reason": "Model actions were sent through the live GenieSim adapter; metrics are computed from returned poses and collisions.",
        "model_evaluation": result,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--vision", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, default=None)
    parser.add_argument("--base-url", default="http://127.0.0.1:5802")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--sidecar-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--eval-result", type=Path, default=None)
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--model-max-length", type=int, default=4096)
    parser.add_argument(
        "--decoder",
        choices=("generate", "forward"),
        default="generate",
        help="Autoregressive generation or one-step greedy logits decoding.",
    )
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--run-tag", default=None, help="Unique adapter episode tag; defaults to the current epoch second.")
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    sidecar_dir = args.sidecar_dir.expanduser().resolve()
    output = args.output.expanduser().resolve()
    base = args.base.expanduser().resolve()
    vision = args.vision.expanduser().resolve()
    adapter = args.adapter.expanduser().resolve() if args.adapter else None
    metadata_rows = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(sidecar_dir.glob("eval-*.json"))]
    metadata_rows = metadata_rows[: args.limit]
    if len(metadata_rows) != args.limit:
        raise RuntimeError(f"expected {args.limit} held-out sidecars, found {len(metadata_rows)}")

    health = request_json(args.base_url, "/health")
    if not health.get("ready"):
        raise RuntimeError(f"GenieSim adapter is not ready: {health}")
    runner = StreamVLNRunner(
        repo=args.repo.expanduser().resolve(),
        root=root,
        base=base,
        vision=vision,
        adapter=adapter,
        max_length=args.model_max_length,
        decoder=args.decoder,
    )
    run_tag = re.sub(r"[^A-Za-z0-9_-]", "", args.run_tag or str(int(time.time())))
    rows: list[dict[str, Any]] = []
    for index, metadata in enumerate(metadata_rows, start=1):
        print(json.dumps({"event": "episode_start", "variant": runner.variant, "index": index, "episode_id": metadata["episode_id"]}), flush=True)
        row = run_episode(
            runner=runner,
            base_url=args.base_url,
            root=root,
            metadata=metadata,
            max_steps=args.max_steps,
            run_tag=run_tag,
        )
        rows.append(row)
        print(json.dumps({"event": "episode_done", "variant": runner.variant, **{k: row[k] for k in ("episode_id", "success_0_5", "final_distance_to_goal", "collisions", "steps")}}, ensure_ascii=False), flush=True)

    summary = summarize_runs(rows)
    result = {
        "schema_version": "geniesim-streamvln/v1",
        "metric_source": "eval_result.json",
        "status": "passed",
        "variant": runner.variant,
        "official": False,
        "same_heldout_batch": True,
        "episode_ids": [str(row["episode_id"]) for row in rows],
        "geniesim_health": health,
        "summary": summary,
        "model": {
            "base": str(base),
            "vision": str(vision),
            "adapter": str(adapter) if adapter else None,
            "streamvln_repo": str(args.repo.expanduser().resolve()),
            "compatibility": runner.compatibility,
            "vision_weights": runner.vision_weights,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.eval_result:
        update_eval_result(args.eval_result.expanduser().resolve(), runner.variant, result)
    print(json.dumps({"event": "evaluation_done", "variant": runner.variant, "output": str(output), "episodes": len(rows), "success_0_5": summary["success_0_5"], "mean_spl_0_5": summary["mean_spl_0_5"]}), flush=True)


if __name__ == "__main__":
    main()
