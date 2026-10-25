"""Dedicated CPU integration gate; explicitly invoke with STREAMVLN_REPO set.

This tests the migrated software with tiny random local models. It is not a
CUDA, real-checkpoint, actual-data, or navigation-success acceptance test.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import warnings

from tests import model_stack_fixtures as fixtures


def setUpModule():
    fixtures.activate_upstream()


class ModelStackIntegrationTests(unittest.TestCase):
    def setUp(self):
        import torch

        torch.manual_seed(371)
        self.temporary = tempfile.TemporaryDirectory(prefix="streamvln-tiny-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.vision = fixtures.create_vision(self.root)
        self.model = fixtures.create_model(self.vision)

    def test_multiframe_and_memory_forward_backward_have_real_gradients(self):
        import torch

        self.model.train()
        for dtype in (torch.float32, torch.bfloat16):
            self.model.to(dtype=dtype)
            for history in (False, True):
                with self.subTest(history=history, dtype=str(dtype)):
                    self.model.zero_grad(set_to_none=True)
                    data = fixtures.batch(history=history)
                    data["images"] = data["images"].to(dtype=dtype)
                    outputs = self.model(**data)
                    self.assertTrue(torch.isfinite(outputs.loss).item())
                    self.assertGreater(outputs.loss.item(), 0)
                    self.assertEqual(outputs.logits.shape, (1, 12, 64))
                    outputs.loss.backward()
                    for name in ("model.mm_projector.weight", "model.layers.0.self_attn.q_proj.weight"):
                        gradient = dict(self.model.named_parameters())[name].grad
                        self.assertIsNotNone(gradient, name)
                        self.assertTrue(torch.isfinite(gradient).all().item(), name)
                        self.assertGreater(gradient.abs().sum().item(), 0, name)
                    self.assertTrue(all(parameter.grad is None for parameter in self.model.get_vision_tower().parameters()))

    def test_loss_uses_num_items_in_batch_for_accumulation_normalization(self):
        import torch
        import torch.nn.functional as functional

        self.model.eval()
        data = fixtures.batch()
        prepared = self.model.prepare_inputs_labels_for_multimodal(
            data["input_ids"], None, data["attention_mask"], None, data["labels"],
            data["images"], None, None, None, None, data["time_ids"], data["task_type"],
        )
        expanded_labels = prepared[-1]
        count = (expanded_labels[:, 1:] != -100).sum()
        outputs = self.model(**data, num_items_in_batch=count * 2)
        expected = functional.cross_entropy(
            outputs.logits[:, :-1, :].contiguous().view(-1, outputs.logits.shape[-1]),
            expanded_labels[:, 1:].contiguous().view(-1),
            ignore_index=-100,
            reduction="sum",
        ) / (count * 2)
        torch.testing.assert_close(outputs.loss, expected)
        outputs.loss.backward()
        actual_gradient = self.model.lm_head.weight.grad.detach().clone()
        self.model.zero_grad(set_to_none=True)
        reference = self.model(**data).loss / 2
        reference.backward()
        torch.testing.assert_close(actual_gradient, self.model.lm_head.weight.grad, rtol=1e-5, atol=1e-7)

    def test_base_checkpoint_preserves_embedded_vision_weights(self):
        import torch

        self.model.eval()
        weight_name = "vision_model.embeddings.patch_embedding.weight"
        tower = self.model.get_vision_tower().vision_tower
        original = dict(tower.named_parameters())[weight_name].detach().clone()
        with torch.no_grad():
            dict(tower.named_parameters())[weight_name][0].add_(1.0)
        expected = dict(tower.named_parameters())[weight_name].detach().clone()
        self.assertFalse(torch.equal(original, expected))
        base = self.root / "embedded-vision-base"
        self.model.save_pretrained(base, safe_serialization=True)
        with torch.no_grad():
            expected_logits = self.model(**fixtures.batch()).logits
        loaded = fixtures.load_model(base)
        actual = dict(loaded.get_vision_tower().vision_tower.named_parameters())[weight_name]
        torch.testing.assert_close(actual, expected, rtol=0, atol=0)
        loaded.eval()
        with torch.no_grad():
            torch.testing.assert_close(loaded(**fixtures.batch()).logits, expected_logits, rtol=1e-5, atol=1e-6)

    def test_indexed_vision_restore_preserves_language_only_lora(self):
        import torch
        from peft import LoraConfig, get_peft_model
        from llava.model.language_model.llava_qwen import restore_streamvln_vision_weights

        with torch.no_grad():
            self.model.get_vision_tower().vision_tower.vision_model.embeddings.patch_embedding.weight[0].add_(1.0)
        base = self.root / "sharded-base"
        self.model.save_pretrained(base, safe_serialization=True)
        fixtures.write_sharded_checkpoint(base, self.model.state_dict())
        delayed = fixtures.load_model(base, load_vision=False)
        self.assertFalse(delayed.get_vision_tower().is_loaded)
        model = get_peft_model(delayed, LoraConfig(
            r=2, lora_alpha=4, lora_dropout=0.0,
            target_modules=["q_proj", "v_proj"], task_type="CAUSAL_LM",
        ))
        digest = fixtures.adapter_digest(model)
        report = restore_streamvln_vision_weights(model, base)
        self.assertEqual(report["status"], "restored")
        self.assertGreater(report["tensor_count"], 0)
        self.assertEqual(report["prefix"], "model.vision_tower.")
        self.assertEqual(fixtures.adapter_digest(model), digest)
        self.assertFalse(any("lora_" in name for name, _ in model.get_vision_tower().named_parameters()))
        for name, expected in self.model.get_vision_tower().state_dict().items():
            torch.testing.assert_close(model.get_vision_tower().state_dict()[name], expected, rtol=0, atol=0)

    def test_vision_restore_rejects_incomplete_or_unsafe_checkpoint_index(self):
        import torch
        from safetensors.torch import save_file
        from llava.model.language_model.llava_qwen import restore_streamvln_vision_weights

        tensors = self.model.state_dict()
        vision_name = next(name for name in tensors if name.startswith("model.vision_tower."))
        language_name = next(name for name in tensors if not name.startswith("model.vision_tower."))
        original = {name: tensor.detach().clone() for name, tensor in self.model.get_vision_tower().state_dict().items()}
        cases = ("partial", "missing", "escape", "unsafe_language", "symlink", "ambiguous", "shape")
        for case in cases:
            with self.subTest(case=case):
                base = self.root / case
                index = fixtures.write_sharded_checkpoint(base, tensors)
                if case == "partial":
                    del index["weight_map"][vision_name]
                elif case == "missing":
                    index["weight_map"][vision_name] = "absent.safetensors"
                elif case == "escape":
                    index["weight_map"][vision_name] = "../outside.safetensors"
                elif case == "unsafe_language":
                    index["weight_map"][language_name] = "../outside.safetensors"
                elif case == "symlink":
                    outside = self.root / "outside.safetensors"
                    save_file({vision_name: tensors[vision_name]}, outside)
                    (base / "linked.safetensors").symlink_to(outside)
                    index["weight_map"][vision_name] = "linked.safetensors"
                elif case == "ambiguous":
                    save_file(tensors, base / "model.safetensors")
                elif case == "shape":
                    visual = {name: tensor for name, tensor in tensors.items() if name.startswith("model.vision_tower.")}
                    visual[vision_name] = torch.zeros((1,), dtype=visual[vision_name].dtype)
                    save_file(visual, base / "vision.safetensors")
                (base / "model.safetensors.index.json").write_text(json.dumps(index), encoding="utf-8")
                with self.assertRaises((ValueError, RuntimeError)):
                    restore_streamvln_vision_weights(self.model, base)
                for name, expected in original.items():
                    torch.testing.assert_close(self.model.get_vision_tower().state_dict()[name], expected, rtol=0, atol=0)

    def test_legacy_flat_qwen_config_preserves_dimensions_and_drives_real_model(self):
        import torch
        from llava.model.language_model.llava_qwen import LlavaQwenConfig, load_streamvln_config

        base, _, _ = fixtures.create_cli_training_case(self.root)
        config = load_streamvln_config(base)
        self.assertIsInstance(config, LlavaQwenConfig)
        self.assertEqual(config.model_type, "llava_qwen")
        self.assertEqual(config.hidden_size, 32)
        self.assertEqual(config.vocab_size, 64)
        self.assertEqual(config.num_hidden_layers, 2)
        self.assertEqual(config.num_attention_heads, 4)
        self.assertEqual(config.num_key_value_heads, 2)
        self.assertEqual(config.rope_parameters["rope_theta"], 1000000.0)
        self.assertIsNone(config.pad_token_id)
        self.assertFalse(hasattr(config, "text_config"))
        model = fixtures.load_model(base)
        self.assertEqual(model.lm_head.out_features, 64)
        self.assertEqual(model.get_input_embeddings().num_embeddings, 64)
        sample = fixtures.batch()
        sample["images"] = torch.nn.functional.interpolate(
            sample["images"].flatten(0, 1), size=(384, 384), mode="nearest",
        ).reshape(1, 2, 3, 384, 384)
        result = model(**sample)
        self.assertTrue(torch.isfinite(result.loss).item())
        result.loss.backward()
        self.assertGreater(model.lm_head.weight.grad.abs().sum().item(), 0)
        model.eval()
        model.reset(1)
        generated = model.generate(
            inputs=sample["input_ids"], images=sample["images"], time_ids=sample["time_ids"],
            task_type=sample["task_type"], env_id=0, min_new_tokens=3, max_new_tokens=3,
            do_sample=False, use_cache=True, return_dict_in_generate=True,
        )
        self.assertEqual(generated.sequences.shape[-1], 3)

    def test_local_qwen_config_rejects_wrong_architecture_or_invalid_dimensions(self):
        from llava.model.language_model.llava_qwen import load_streamvln_config

        location = self.root / "config-boundaries"
        location.mkdir()
        native = self.model.config.to_dict()
        native["model_type"] = "llava_qwen"
        native.pop("architectures", None)
        path = location / "config.json"
        path.write_text(json.dumps(native), encoding="utf-8")
        self.assertEqual(load_streamvln_config(location).vocab_size, 64)
        invalid = (
            {**native, "hidden_size": 0},
            {**native, "hidden_size": True},
            {key: value for key, value in native.items() if key != "num_key_value_heads"},
            {**native, "architectures": ["LlamaForCausalLM"]},
            {**native, "model_type": "llava"},
            {**native, "model_type": "bert", "architectures": ["StreamVLNForCausalLM"]},
        )
        for index, content in enumerate(invalid):
            with self.subTest(case=index):
                path.write_text(json.dumps(content), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_streamvln_config(location)

    def test_generation_handles_multiple_tokens_frames_and_independent_reset(self):
        import torch
        from streamvln.utils.utils import IMAGE_TOKEN_INDEX

        self.model.eval()
        self.model.reset(2)
        self.assertIsNot(self.model.cache[0], self.model.cache[1])
        ids = torch.tensor([[7, IMAGE_TOKEN_INDEX, 8]])
        image = fixtures.batch()["images"][:, :1]
        arguments = dict(
            inputs=ids, images=image, env_id=0, time_ids=[[0]], task_type=[0],
            do_sample=False, max_new_tokens=4, min_new_tokens=4, use_cache=True,
            return_dict_in_generate=True, output_scores=True,
        )
        first = self.model.generate(**arguments)
        self.assertEqual(len(first.scores), 4)
        self.assertIsNotNone(first.past_key_values)
        self.assertTrue(all(torch.isfinite(score).any().item() for score in first.scores))
        first_length = self.model.cache[0]["inputs_embeds"].shape[1]
        for frame in range(1, 8):
            result = self.model.generate(**{**arguments, "time_ids": [[frame]]})
            self.assertEqual(len(result.scores), 4)
            self.assertEqual(self.model.cache[0]["inputs_embeds"].shape[1], first_length * (frame + 1))
        self.assertEqual(self.model.curr_t, [8, 0])
        self.assertEqual(self.model.cache[1], {})
        self.model.generate(**{**arguments, "env_id": 1})
        other_history = self.model.cache[1]["inputs_embeds"].clone()
        # This is the same window boundary used after eight evaluator actions.
        self.model.reset_for_env(0)
        self.assertEqual(self.model.curr_t, [0, 1])
        self.assertEqual(self.model.cache[0], {})
        torch.testing.assert_close(self.model.cache[1]["inputs_embeds"], other_history)
        repeated = self.model.generate(**arguments)
        torch.testing.assert_close(repeated.sequences, first.sequences, rtol=0, atol=0)
        # A new episode clears every environment rather than carrying memory.
        self.model.reset(2)
        self.assertEqual(self.model.curr_t, [0, 0])
        self.assertEqual(self.model.cache, [{}, {}])
        self.assertIsNot(self.model.cache[0], self.model.cache[1])
        new_episode = self.model.generate(**arguments)
        torch.testing.assert_close(new_episode.sequences, first.sequences, rtol=0, atol=0)

    def test_original_training_entrypoint_help_imports_supported_stack(self):
        upstream = Path(os.environ["STREAMVLN_REPO"]).resolve()
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join((str(upstream), str(upstream / "streamvln")))
        process = subprocess.run(
            [sys.executable, str(upstream / "streamvln" / "streamvln_train.py"), "--help"],
            cwd=upstream, env=environment, text=True, capture_output=True, timeout=90,
        )
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertIn("--model_name_or_path", process.stdout)
        self.assertIn("--lora_enable", process.stdout)

    def test_original_training_cli_runs_one_cpu_lora_step_and_saves_final_adapter(self):
        import math
        import torch
        from peft import PeftModel
        from safetensors.torch import load_file
        from llava.model.language_model.llava_qwen import restore_streamvln_vision_weights

        upstream = Path(os.environ["STREAMVLN_REPO"]).resolve()
        base, vision, dataset = fixtures.create_cli_training_case(self.root)
        output = self.root / "cli-training"
        command = [sys.executable, str(upstream / "streamvln" / "streamvln_train.py")]
        options = {
            "model_name_or_path": str(base), "vision_tower": str(vision),
            "video_folder": str(dataset), "output_dir": str(output),
            "version": "qwen_2", "mm_tunable_parts": "mm_lora_layer",
            "mm_use_im_patch_token": "False", "mm_patch_merge_type": "flat",
            "mm_spatial_pool_mode": "average", "image_aspect_ratio": "square",
            "num_frames": "4", "num_history": "1", "num_future_steps": "1",
            "lora_enable": "True", "lora_r": "8", "lora_alpha": "16",
            "lora_dropout": "0.05", "bits": "16", "use_cpu": "True",
            "bf16": "False", "fp16": "False", "tf32": "False",
            "attn_implementation": "eager", "gradient_checkpointing": "True",
            "per_device_train_batch_size": "1", "gradient_accumulation_steps": "1",
            "learning_rate": "0.00002", "max_steps": "1", "num_train_epochs": "1",
            "logging_steps": "1", "save_strategy": "steps", "save_steps": "1",
            "report_to": "none", "disable_tqdm": "True", "dataloader_num_workers": "0",
            "dataloader_pin_memory": "False", "remove_unused_columns": "False",
            "model_max_length": "256",
        }
        command += [item for key, value in options.items() for item in (f"--{key}", value)]
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join((str(upstream), str(upstream / "streamvln")))
        environment["OMP_NUM_THREADS"] = "1"
        environment["MKL_NUM_THREADS"] = "1"
        process = subprocess.run(
            command, cwd=upstream, env=environment, text=True, capture_output=True, timeout=120,
        )
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertIn("Embedded base vision restoration:", process.stdout)
        self.assertIn("'status': 'restored'", process.stdout)
        state = json.loads((output / "trainer_state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["global_step"], 1)
        losses = [entry["loss"] for entry in state["log_history"] if "loss" in entry]
        self.assertTrue(losses)
        self.assertTrue(all(math.isfinite(loss) for loss in losses))
        adapter_path = output / "adapter_model.safetensors"
        self.assertTrue(adapter_path.is_file())
        self.assertTrue((output / "checkpoint-1" / "adapter_model.safetensors").is_file())
        self.assertFalse((output / "adapter_model.bin").exists())
        weights = load_file(adapter_path)
        self.assertTrue(any("lora_B" in name and tensor.abs().sum().item() > 0 for name, tensor in weights.items()))
        self.assertTrue(all(torch.isfinite(tensor).all().item() for tensor in weights.values()))
        # Reload the actual CLI export, not the independently saved test adapter.
        # Match production ordering: attach language LoRA before delayed vision
        # loading, so short target names cannot inject untrained vision LoRA.
        with warnings.catch_warnings(record=True) as captured:
            reloaded = PeftModel.from_pretrained(
                fixtures.load_model(base, load_vision=False), output, local_files_only=True,
            )
        self.assertFalse(any("missing adapter keys" in str(item.message) for item in captured))
        restore_streamvln_vision_weights(reloaded, base)
        self.assertFalse(any("lora_" in name for name, _ in reloaded.get_vision_tower().named_parameters()))
        embedded = load_file(base / "model.safetensors")
        for name, actual in reloaded.get_vision_tower().state_dict().items():
            torch.testing.assert_close(actual, embedded["model.vision_tower." + name], rtol=0, atol=0)
        reloaded.eval()
        sample = fixtures.batch()
        sample["images"] = torch.nn.functional.interpolate(
            sample["images"].flatten(0, 1), size=(384, 384), mode="nearest",
        ).reshape(1, 2, 3, 384, 384)
        with torch.no_grad():
            self.assertTrue(torch.isfinite(reloaded(**sample).loss).item())

    def test_local_tokenizer_preserves_image_ids_and_supervised_label_mask(self):
        import torch
        from transformers import AutoTokenizer
        from adapter.model_closed_loop_eval import StreamVLNRunner
        from streamvln.dataset.vln_action_dataset import preprocess_qwen
        from streamvln.utils.utils import IMAGE_TOKEN_INDEX, MEMORY_TOKEN_INDEX

        fixtures.create_tokenizer(self.root)
        tokenizer = AutoTokenizer.from_pretrained(
            self.root / "tiny-tokenizer", local_files_only=True, trust_remote_code=False,
        )
        before = len(tokenizer)
        result = preprocess_qwen([[
            {"from": "human", "value": "user_only_marker <image> <memory>"},
            {"from": "gpt", "value": "assistant_only_marker forward"},
        ]], tokenizer, has_image=True)
        ids, labels = result["input_ids"], result["labels"]
        self.assertEqual(ids.shape, labels.shape)
        self.assertEqual(len(tokenizer), before)
        self.assertEqual((ids == IMAGE_TOKEN_INDEX).sum().item(), 1)
        self.assertEqual((ids == MEMORY_TOKEN_INDEX).sum().item(), 1)
        for token, expected in (("user_only_marker", -100), ("assistant_only_marker", tokenizer.convert_tokens_to_ids("assistant_only_marker"))):
            positions = ids == tokenizer.convert_tokens_to_ids(token)
            self.assertEqual(positions.sum().item(), 1)
            self.assertEqual(labels[positions].item(), expected)
        self.assertTrue((labels[ids < 0] == -100).all().item())
        self.assertGreater((labels != -100).sum().item(), 0)
        # Exercise the real prompt boundary without constructing the CUDA-only
        # full runner; the tokenizer and tensors are real local dependencies.
        runner = StreamVLNRunner.__new__(StreamVLNRunner)
        runner.tokenizer = tokenizer
        runner.device = torch.device("cpu")
        runner.image_token = "<image>"
        runner.memory_token = "<memory>"
        runner.image_token_index = IMAGE_TOKEN_INDEX
        runner.memory_token_index = MEMORY_TOKEN_INDEX
        initial = runner._prompt_ids("go to red target", 0)
        self.assertIsInstance(initial, torch.Tensor)
        self.assertEqual(initial.ndim, 2)
        self.assertEqual((initial == IMAGE_TOKEN_INDEX).sum().item(), 1)
        self.assertEqual((initial == MEMORY_TOKEN_INDEX).sum().item(), 0)
        historical = runner._prompt_ids("go to red target", 1)
        self.assertEqual((historical == IMAGE_TOKEN_INDEX).sum().item(), 1)
        self.assertEqual((historical == MEMORY_TOKEN_INDEX).sum().item(), 1)
        self.assertEqual(runner._last_input_length, historical.shape[1])

    def test_lora_safetensors_round_trip_in_a_fresh_process(self):
        import torch
        from peft import LoraConfig, get_peft_model
        from safetensors.torch import save_file

        with torch.no_grad():
            self.model.get_vision_tower().vision_tower.vision_model.embeddings.patch_embedding.weight[0].add_(1.0)
        self.model.save_pretrained(self.root / "base", safe_serialization=True)
        model = get_peft_model(self.model, LoraConfig(
            r=2, lora_alpha=4, lora_dropout=0.0,
            target_modules=r"model\.layers\.\d+\.self_attn\.(q_proj|v_proj)", task_type="CAUSAL_LM",
        ))
        optimizer = torch.optim.SGD((p for p in model.parameters() if p.requires_grad), lr=0.1)
        before = fixtures.adapter_digest(model)
        model.train()
        model(**fixtures.batch()).loss.backward()
        optimizer.step()
        self.assertNotEqual(fixtures.adapter_digest(model), before)
        model.eval()
        with torch.no_grad():
            logits = model(**fixtures.batch()).logits
        sequences = fixtures.generate_once(model)
        self.assertEqual(sequences.shape[-1], 3)
        save_file({"logits": logits.contiguous(), "sequences": sequences.contiguous()}, self.root / "expected.safetensors")
        model.save_pretrained(self.root / "adapter", safe_serialization=True)
        self.assertTrue((self.root / "adapter" / "adapter_model.safetensors").is_file())
        self.assertFalse((self.root / "adapter" / "adapter_model.bin").exists())
        process = subprocess.run(
            [sys.executable, "-m", "tests.model_stack_fixtures", "--reload", str(self.root)],
            cwd=Path(__file__).resolve().parents[1], env=os.environ.copy(),
            text=True, capture_output=True, timeout=90,
        )
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        result = json.loads(process.stdout.strip().splitlines()[-1])
        self.assertEqual(result["adapter_digest"], fixtures.adapter_digest(model))
        self.assertEqual(result["device"], "cpu")

    def test_supported_trainer_runs_accumulation_and_saves_checkpoints(self):
        import torch
        from peft import LoraConfig, get_peft_model
        from llava.train.llava_trainer import LLaVATrainer
        from streamvln.args import TrainingArguments

        model = get_peft_model(self.model, LoraConfig(
            r=2, lora_alpha=4, lora_dropout=0.0,
            target_modules=r"model\.layers\.\d+\.self_attn\.(q_proj|v_proj)", task_type="CAUSAL_LM",
        ))
        model.enable_input_require_grads()
        before = fixtures.adapter_digest(model)
        output = self.root / "training"
        arguments = TrainingArguments(
            output_dir=str(output), use_cpu=True, bf16=False, fp16=False,
            max_steps=2, per_device_train_batch_size=1, gradient_accumulation_steps=2,
            learning_rate=0.01, save_strategy="steps", save_steps=1,
            logging_strategy="steps", logging_steps=1, report_to="none",
            disable_tqdm=True, dataloader_num_workers=0, dataloader_pin_memory=False,
            remove_unused_columns=False, gradient_checkpointing=True,
            gradient_checkpointing_kwargs={"use_reentrant": False},
        )
        arguments.mm_tunable_parts = "mm_lora_layer"
        trainer = LLaVATrainer(
            model=model, args=arguments,
            train_dataset=[fixtures.batch(offset=i) for i in range(4)],
            data_collator=fixtures.collate_rows,
        )
        result = trainer.train()
        self.assertEqual(trainer.state.global_step, 2)
        self.assertTrue(torch.isfinite(torch.tensor(result.training_loss)).item())
        self.assertNotEqual(fixtures.adapter_digest(model), before)
        for step in (1, 2):
            checkpoint = output / f"checkpoint-{step}"
            self.assertTrue((checkpoint / "adapter_model.safetensors").is_file())
            self.assertTrue((checkpoint / "trainer_state.json").is_file())
            self.assertFalse((checkpoint / "adapter_model.bin").exists())
        trainer.save_model(str(output / "final"))
        self.assertTrue((output / "final" / "adapter_model.safetensors").is_file())

    def test_trainer_accumulation_matches_one_combined_batch_with_unequal_labels(self):
        import torch
        from llava.train.llava_trainer import LLaVATrainer
        from streamvln.args import TrainingArguments

        rows = [fixtures.batch(offset=i) for i in range(2)]
        rows[1]["labels"][:, -2] = -100
        combined = copy.deepcopy(self.model)
        accumulated = copy.deepcopy(self.model)
        for name, model, batch_size, accumulation in (
            ("combined", combined, 2, 1), ("accumulated", accumulated, 1, 2),
        ):
            arguments = TrainingArguments(
                output_dir=str(self.root / name), use_cpu=True, bf16=False, fp16=False,
                max_steps=1, per_device_train_batch_size=batch_size,
                gradient_accumulation_steps=accumulation, learning_rate=0.01,
                optim="sgd", lr_scheduler_type="constant", weight_decay=0.0,
                max_grad_norm=0.0, save_strategy="no", logging_strategy="no",
                report_to="none", disable_tqdm=True, dataloader_num_workers=0,
                dataloader_pin_memory=False, remove_unused_columns=False,
                gradient_checkpointing=False,
            )
            arguments.mm_tunable_parts = "mm_lora_layer"
            trainer = LLaVATrainer(
                model=model, args=arguments, train_dataset=rows, data_collator=fixtures.collate_rows,
            )
            trainer.train()
        for name, expected in combined.named_parameters():
            torch.testing.assert_close(
                dict(accumulated.named_parameters())[name], expected, rtol=1e-5, atol=1e-7,
                msg=lambda message, name=name: f"Accumulation changed parameter {name}: {message}",
            )

    def test_trainer_rejects_unsupported_modes_including_explicit_zero_learning_rate(self):
        from llava.train.llava_trainer import LLaVATrainer
        from streamvln.args import TrainingArguments

        for option in ({"group_by_task": True}, {"mm_projector_lr": 0.0}):
            with self.subTest(option=option):
                arguments = TrainingArguments(
                    output_dir=str(self.root / "unsupported"), use_cpu=True,
                    bf16=False, fp16=False, report_to="none", **option,
                )
                with self.assertRaisesRegex(ValueError, "outside"):
                    LLaVATrainer(model=self.model, args=arguments)


if __name__ == "__main__":
    unittest.main()
