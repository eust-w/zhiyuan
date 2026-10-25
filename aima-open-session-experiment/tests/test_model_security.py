import ast
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "adapter" / "model_security.py"
if MODULE_PATH.is_file():
    from adapter import model_security
else:
    model_security = None


class ModelSecurityTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(model_security, "local safetensors validation is missing")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.model = self.root / "model"
        self.model.mkdir()
        (self.model / "config.json").write_text("{}", encoding="utf-8")

    def test_single_safetensors_file_is_accepted(self):
        weight = self.model / "model.safetensors"
        weight.write_bytes(b"test fixture, not a tensor payload")
        self.assertEqual(model_security.validate_model_directory(self.model), (weight,))

    def test_model_rejects_adapter_config_redirection(self):
        (self.model / "model.safetensors").write_bytes(b"safe")
        redirect = self.model / "adapter_config.json"
        target = self.root / "redirect.json"
        target.write_text('{"base_model_name_or_path":"/unchecked/model"}')
        for kind in ("file", "symlink", "dangling_symlink"):
            with self.subTest(kind=kind):
                if kind == "file":
                    redirect.write_text(target.read_text())
                else:
                    redirect.symlink_to(target if kind == "symlink" else self.root / "missing.json")
                try:
                    with self.assertRaisesRegex(ValueError, "adapter_config|redirection"):
                        model_security.validate_model_directory(self.model)
                finally:
                    redirect.unlink()

    def test_sharded_index_checks_all_local_shards(self):
        first = self.model / "model-1.safetensors"
        second = self.model / "model-2.safetensors"
        first.write_bytes(b"one")
        second.write_bytes(b"two")
        (self.model / "model.safetensors.index.json").write_text(json.dumps({
            "weight_map": {"a": first.name, "b": second.name, "c": first.name}
        }), encoding="utf-8")
        self.assertEqual(model_security.validate_model_directory(self.model), (first, second))

    def test_missing_shard_is_rejected(self):
        (self.model / "model.safetensors.index.json").write_text(
            json.dumps({"weight_map": {"a": "missing.safetensors"}}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "missing|empty"):
            model_security.validate_model_directory(self.model)

    def test_pickle_only_model_is_rejected(self):
        (self.model / "pytorch_model.bin").write_bytes(b"pickle")
        with self.assertRaisesRegex(ValueError, "pickle|safetensors"):
            model_security.validate_model_directory(self.model)

    def test_mixed_pickle_model_is_rejected_for_external_vision_loader(self):
        (self.model / "model.safetensors").write_bytes(b"safe")
        (self.model / "pytorch_model.bin").write_bytes(b"pickle")
        with self.assertRaisesRegex(ValueError, "pickle"):
            model_security.validate_model_directory(self.model)

    def test_index_traversal_absolute_and_non_safetensors_are_rejected(self):
        outside = self.root / "outside.safetensors"
        outside.write_bytes(b"outside")
        for filename in ("../outside.safetensors", str(outside), "weights.bin"):
            with self.subTest(filename=filename):
                (self.model / "model.safetensors.index.json").write_text(
                    json.dumps({"weight_map": {"a": filename}}), encoding="utf-8")
                with self.assertRaises(ValueError):
                    model_security.validate_model_directory(self.model)

    def test_symlinked_weight_or_index_cannot_escape_model_directory(self):
        outside = self.root / "outside.safetensors"
        outside.write_bytes(b"outside")
        link = self.model / "model.safetensors"
        link.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "outside"):
            model_security.validate_model_directory(self.model)
        link.unlink()
        outside_index = self.root / "index.json"
        outside_index.write_text('{"weight_map":{"a":"model-1.safetensors"}}')
        (self.model / "model.safetensors.index.json").symlink_to(outside_index)
        with self.assertRaisesRegex(ValueError, "outside"):
            model_security.validate_model_directory(self.model)

    def test_empty_or_malformed_index_is_rejected(self):
        index = self.model / "model.safetensors.index.json"
        for content in ('{}', '{"weight_map":{}}', '{"weight_map":{"a":null}}', '[]', 'bad json'):
            with self.subTest(content=content):
                index.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    model_security.validate_model_directory(self.model)

    def test_config_symlink_cannot_escape(self):
        (self.model / "config.json").unlink()
        outside = self.root / "outside.json"
        outside.write_text("{}", encoding="utf-8")
        (self.model / "config.json").symlink_to(outside)
        (self.model / "model.safetensors").write_bytes(b"safe")
        with self.assertRaisesRegex(ValueError, "outside"):
            model_security.validate_model_directory(self.model)

    def test_adapter_requires_safetensors(self):
        (self.model / "adapter_config.json").write_text('{"base_model_name_or_path":"/local/model"}')
        (self.model / "adapter_model.bin").write_bytes(b"pickle")
        with self.assertRaisesRegex(ValueError, "pickle|safetensors"):
            model_security.validate_adapter_directory(self.model)
        (self.model / "adapter_model.bin").unlink()
        (self.model / "adapter_model.safetensors").write_bytes(b"safe")
        self.assertEqual(model_security.validate_adapter_directory(self.model)["base_model_name_or_path"], "/local/model")

    def test_adapter_training_metadata_is_not_loaded_or_blocking(self):
        (self.model / "adapter_config.json").write_text("{}")
        (self.model / "adapter_model.safetensors").write_bytes(b"safe")
        (self.model / "training_args.bin").write_bytes(b"metadata, not adapter weights")
        try:
            config = model_security.validate_adapter_directory(self.model)
        except ValueError as exc:
            self.fail(f"unused trainer metadata must not block safe adapter weights: {exc}")
        self.assertEqual(config, {})

    def test_vision_config_requires_local_validated_weights(self):
        (self.model / "config.json").write_text('{"mm_vision_tower":"remote/model"}')
        with self.assertRaises(ValueError):
            model_security.resolve_vision_directory(self.model)
        vision = self.root / "vision"
        vision.mkdir()
        (vision / "config.json").write_text("{}")
        (vision / "model.safetensors").write_bytes(b"safe")
        (self.model / "config.json").write_text(json.dumps({"mm_vision_tower": str(vision)}))
        self.assertEqual(model_security.resolve_vision_directory(self.model), vision)

    def test_vision_alias_must_point_to_validated_directory(self):
        (self.model / "model.safetensors").write_bytes(b"safe")
        alias = self.root / "siglip-local"
        other = self.root / "other"
        other.mkdir()
        alias.symlink_to(other, target_is_directory=True)
        self.assertTrue(hasattr(model_security, "vision_model_name"), "safe vision alias is missing")
        with self.assertRaisesRegex(ValueError, "alias"):
            model_security.vision_model_name(self.model)
        alias.unlink()
        self.assertEqual(model_security.vision_model_name(self.model), str(alias))
        self.assertEqual(alias.resolve(), self.model)

    def test_stage2_checkpoint_gate_accepts_single_and_rejects_missing_shard(self):
        from adapter import stage2_preflight
        self.assertTrue(hasattr(stage2_preflight, "checkpoint_safety_gate"), "training safetensors gate is missing")
        (self.model / "model.safetensors").write_bytes(b"safe")
        (self.model / "config.json").write_text(json.dumps({"mm_vision_tower": str(self.model)}))
        self.assertEqual(stage2_preflight.checkpoint_safety_gate(self.model, self.model)["status"], "ready")
        (self.model / "model.safetensors").unlink()
        (self.model / "model.safetensors.index.json").write_text(
            json.dumps({"weight_map": {"a": "missing.safetensors"}}), encoding="utf-8")
        self.assertEqual(stage2_preflight.checkpoint_safety_gate(self.model, self.model)["status"], "blocked")

    def test_stage2_rejects_unchecked_vision_reference_in_base_config(self):
        from adapter.stage2_preflight import checkpoint_safety_gate
        (self.model / "model.safetensors").write_bytes(b"safe")
        other = self.root / "other-vision"
        other.mkdir()
        (other / "config.json").write_text("{}")
        (other / "model.safetensors").write_bytes(b"other weights")
        unsafe_configs = (
            {"mm_vision_tower": str(other)},
            {"mm_vision_tower": "unreviewed/remote-vision"},
            {"mm_vision_tower": str(self.root / "missing-vision")},
            {"mm_vision_tower": str(self.model), "vision_tower": str(other)},
            {"vision_tower": str(other)},
            {},
            {"mm_vision_tower": None, "vision_tower": str(self.model)},
            {"mm_vision_tower": "", "vision_tower": str(self.model)},
            {"mm_vision_tower": [str(self.model)]},
        )
        for config in unsafe_configs:
            with self.subTest(config=config):
                (self.model / "config.json").write_text(json.dumps(config))
                result = checkpoint_safety_gate(self.model, self.model)
                self.assertEqual(result["status"], "blocked")
                self.assertIn("vision", result["error"])

    def test_stage2_accepts_matching_vision_alias_without_mutating_config(self):
        from adapter.stage2_preflight import checkpoint_safety_gate
        (self.model / "model.safetensors").write_bytes(b"safe")
        alias = self.root / "vision-alias"
        alias.symlink_to(self.model, target_is_directory=True)
        for config in (
            {"mm_vision_tower": str(self.model)},
            {"vision_tower": str(self.model)},
            {"mm_vision_tower": str(alias), "vision_tower": str(self.model)},
        ):
            with self.subTest(config=config):
                before = json.dumps(config)
                (self.model / "config.json").write_text(before)
                self.assertEqual(checkpoint_safety_gate(self.model, alias)["status"], "ready")
                self.assertEqual((self.model / "config.json").read_text(), before)

    def test_qwen_alias_cannot_redirect_checked_checkpoint(self):
        from adapter.stage2_preflight import _qwen_compat_checkpoint
        alias = self.root / "model-qwen-compat"
        other = self.root / "other"
        other.mkdir()
        alias.symlink_to(other, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "checkpoint|alias"):
            _qwen_compat_checkpoint(self.model)

    def test_index_shard_symlink_cannot_escape(self):
        outside = self.root / "outside.safetensors"
        outside.write_bytes(b"outside")
        (self.model / "model-1.safetensors").symlink_to(outside)
        (self.model / "model.safetensors.index.json").write_text(
            json.dumps({"weight_map": {"a": "model-1.safetensors"}}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "outside"):
            model_security.validate_model_directory(self.model)


class ModelLoadingIntegrationTests(unittest.TestCase):
    def test_reload_rejects_pickle_before_importing_external_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            adapter = root / "adapter"
            base = root / "base"
            adapter.mkdir()
            base.mkdir()
            (adapter / "adapter_config.json").write_text(json.dumps({"base_model_name_or_path": str(base)}))
            (adapter / "adapter_model.bin").write_bytes(b"not safe")
            result = subprocess.run([sys.executable, str(ROOT / "adapter/reload_adapter.py"),
                                     "--repo", str(root / "untrusted_repo"), "--adapter", str(adapter)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("safetensors", result.stderr)
            self.assertNotIn("No module named 'torch'", result.stderr)

    def test_owned_model_loaders_disable_unsafe_and_remote_loading(self):
        for filename in ("reload_adapter.py", "model_closed_loop_eval.py"):
            tree = ast.parse((ROOT / "adapter" / filename).read_text())
            found = 0
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                if node.func.attr != "from_pretrained" or not isinstance(node.func.value, ast.Name):
                    continue
                name = node.func.value.id
                kwargs = {kw.arg: kw.value for kw in node.keywords}
                if name in {"AutoConfig", "AutoTokenizer", "StreamVLNForCausalLM", "PeftModel"}:
                    found += 1
                    self.assertIs(getattr(kwargs.get("local_files_only"), "value", None), True, filename)
                if name in {"AutoConfig", "AutoTokenizer", "StreamVLNForCausalLM"}:
                    self.assertIs(getattr(kwargs.get("trust_remote_code"), "value", None), False, filename)
                if name == "StreamVLNForCausalLM":
                    self.assertIs(getattr(kwargs.get("use_safetensors"), "value", None), True, filename)
            self.assertGreaterEqual(found, 3)

    def test_numpy_depth_load_explicitly_disables_pickle(self):
        tree = ast.parse((ROOT / "adapter/model_closed_loop_eval.py").read_text())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute) and node.func.attr == "load"
                 and isinstance(node.func.value, ast.Name) and node.func.value.id == "np"]
        self.assertEqual(len(calls), 1)
        self.assertIs(next((kw.value.value for kw in calls[0].keywords if kw.arg == "allow_pickle"), None), False)


if __name__ == "__main__":
    unittest.main()
