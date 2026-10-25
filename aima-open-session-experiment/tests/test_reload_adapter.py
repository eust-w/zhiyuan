import ast
import builtins
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from adapter import reload_adapter


class ReloadAdapterTests(unittest.TestCase):
    def test_reload_restores_base_vision_after_peft_before_reporting_success(self):
        tree = ast.parse(Path(reload_adapter.__file__).read_text())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        restores = [node for node in calls if isinstance(node.func, ast.Name)
                    and node.func.id == "restore_streamvln_vision_weights"]
        self.assertEqual(len(restores), 1)
        restore = restores[0]
        self.assertEqual([argument.id for argument in restore.args], ["model", "base"])
        peft = next(node for node in calls if isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == "PeftModel"
                    and node.func.attr == "from_pretrained")
        self.assertGreater(restore.lineno, peft.lineno)
        self.assertFalse(any(isinstance(node.func, ast.Attribute) and node.func.attr == "load_model"
                             for node in calls))
        evaluation = next(node for node in calls if isinstance(node.func, ast.Attribute)
                          and isinstance(node.func.value, ast.Name) and node.func.value.id == "model"
                          and node.func.attr == "eval")
        self.assertLess(restore.lineno, evaluation.lineno)
        self.assertTrue(any(isinstance(node, ast.Dict) and any(isinstance(key, ast.Constant)
                            and key.value == "vision_weights" for key in node.keys) for node in ast.walk(tree)))

    def test_reload_reads_legacy_qwen_config_without_autoconfig_dispatch(self):
        tree = ast.parse(Path(reload_adapter.__file__).read_text())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        config_calls = [node for node in calls if isinstance(node.func, ast.Name)
                        and node.func.id == "load_streamvln_config"]
        self.assertEqual(len(config_calls), 1)
        gate = next(node for node in calls if isinstance(node.func, ast.Name)
                    and node.func.id == "prepare_checkout")
        self.assertGreater(config_calls[0].lineno, gate.lineno)
        self.assertFalse(any(isinstance(node.func, ast.Attribute)
                             and isinstance(node.func.value, ast.Name)
                             and node.func.value.id == "AutoConfig" for node in calls))

    def test_reload_checks_compatibility_before_external_imports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, vision, adapter = root / "base", root / "siglip", root / "adapter"
            for directory in (base, vision, adapter):
                directory.mkdir()
            for directory in (base, vision):
                (directory / "config.json").write_text("{}")
                (directory / "model.safetensors").write_bytes(b"format guard fixture")
            (adapter / "adapter_config.json").write_text(json.dumps({"base_model_name_or_path": str(base)}))
            (adapter / "adapter_model.safetensors").write_bytes(b"format guard fixture")
            argv = ["reload", "--repo", str(root / "unreviewed"), "--adapter", str(adapter), "--vision", str(vision)]
            original_import = builtins.__import__

            def reject_external(name, *args, **kwargs):
                if name.split(".")[0] in {"torch", "peft", "transformers", "streamvln", "llava"}:
                    raise AssertionError("external code imported before compatibility gate")
                return original_import(name, *args, **kwargs)

            with patch.object(sys, "argv", argv), patch.object(sys, "path", list(sys.path)), \
                    patch.dict(os.environ), \
                    patch.object(reload_adapter, "prepare_checkout", create=True,
                                 side_effect=ValueError("unreviewed checkout rejected")), \
                    patch("builtins.__import__", side_effect=reject_external):
                try:
                    reload_adapter.main()
                except Exception as exc:
                    self.assertEqual(str(exc), "unreviewed checkout rejected")
                else:
                    self.fail("unreviewed source was not rejected")

    def test_reload_uses_modern_dtype_contract(self):
        tree = ast.parse(Path(reload_adapter.__file__).read_text())
        loader = next(node for node in ast.walk(tree) if isinstance(node, ast.Call)
                      and isinstance(node.func, ast.Attribute) and node.func.attr == "from_pretrained"
                      and isinstance(node.func.value, ast.Name) and node.func.value.id == "StreamVLNForCausalLM")
        self.assertIn("dtype", {kw.arg for kw in loader.keywords})
        self.assertNotIn("torch_dtype", {kw.arg for kw in loader.keywords})
        self.assertNotIn("low_cpu_mem_usage", {kw.arg for kw in loader.keywords})


if __name__ == "__main__":
    unittest.main()
