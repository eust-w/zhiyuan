import ast
import builtins
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from adapter import model_closed_loop_eval
from adapter.model_closed_loop_eval import StreamVLNRunner, path_length, pose_xy


class ModelClosedLoopEvalTests(unittest.TestCase):
    def test_runner_restores_base_vision_after_peft_without_later_tower_reload(self):
        tree = ast.parse(Path(model_closed_loop_eval.__file__).read_text())
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

    def test_runner_reads_legacy_qwen_config_without_autoconfig_dispatch(self):
        tree = ast.parse(Path(model_closed_loop_eval.__file__).read_text())
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

    def test_prompt_requests_token_ids_not_transformers5_batch_encoding(self):
        class TokenIds(np.ndarray):
            def to(self, device):
                return self

        class TemplateTokenizer:
            def apply_chat_template(self, messages, **kwargs):
                # Transformers 5 defaults to a mapping; the entrypoint needs a
                # tensor because it remaps visual tokens using tensor indexing.
                self.kwargs = kwargs
                return np.array([[7, 10, 11, 8]]).view(TokenIds)

            def convert_tokens_to_ids(self, token):
                return {"<image>": 10, "<memory>": 11}[token]

        runner = StreamVLNRunner.__new__(StreamVLNRunner)
        runner.tokenizer = TemplateTokenizer()
        runner.image_token, runner.memory_token = "<image>", "<memory>"
        runner.image_token_index, runner.memory_token_index = -200, -300
        runner.device = "cpu"
        ids = runner._prompt_ids("Go to the red marker.", 1)
        self.assertIs(runner.tokenizer.kwargs.get("return_dict"), False)
        self.assertEqual(ids.tolist(), [[7, -200, -300, 8]])
        self.assertEqual(runner._last_input_length, 4)

    def test_runner_checks_compatibility_before_external_imports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("base", "siglip"):
                directory = root / name
                directory.mkdir()
                (directory / "config.json").write_text("{}")
                (directory / "model.safetensors").write_bytes(b"format guard fixture")
            original_import = builtins.__import__

            def reject_external(name, *args, **kwargs):
                if name.split(".")[0] in {"torch", "peft", "transformers", "streamvln", "llava"}:
                    raise AssertionError("external code imported before compatibility gate")
                return original_import(name, *args, **kwargs)

            with patch.object(model_closed_loop_eval, "prepare_checkout", create=True,
                              side_effect=ValueError("unreviewed checkout rejected")), \
                    patch("builtins.__import__", side_effect=reject_external), \
                    patch.object(sys, "path", list(sys.path)), patch.dict(os.environ):
                try:
                    StreamVLNRunner(repo=root / "unreviewed", root=root, base=root / "base",
                                    vision=root / "siglip", adapter=None, max_length=128)
                except Exception as exc:
                    self.assertEqual(str(exc), "unreviewed checkout rejected")
                else:
                    self.fail("unreviewed source was not rejected")

    def test_runner_uses_modern_dtype_and_cache_contract(self):
        tree = ast.parse(Path(model_closed_loop_eval.__file__).read_text())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute)]
        loader = next(node for node in calls if node.func.attr == "from_pretrained"
                      and isinstance(node.func.value, ast.Name)
                      and node.func.value.id == "StreamVLNForCausalLM")
        self.assertIn("dtype", {kw.arg for kw in loader.keywords})
        self.assertNotIn("torch_dtype", {kw.arg for kw in loader.keywords})
        self.assertNotIn("low_cpu_mem_usage", {kw.arg for kw in loader.keywords})
        tokenizer_loader = next(node for node in calls if node.func.attr == "from_pretrained"
                                and isinstance(node.func.value, ast.Name)
                                and node.func.value.id == "AutoTokenizer")
        self.assertNotIn("use_fast", {kw.arg for kw in tokenizer_loader.keywords})
        generator = next(node for node in calls if node.func.attr == "generate")
        self.assertNotIn("return_legacy_cache", {kw.arg for kw in generator.keywords})

    def test_parser_keeps_model_action_order_and_falls_back_to_stop(self):
        self.assertEqual(StreamVLNRunner.parse_actions("assistant\n→→↑←STOP"), [3, 1, 2, 0])
        self.assertEqual(StreamVLNRunner.parse_actions("no valid action"), [0])

    def test_pose_and_path_length_use_xy_translation(self):
        first = {"pose_matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]}
        second = {"pose_matrix": [1, 0, 0, 1, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]}
        third = {"pose_matrix": [1, 0, 0, 1, 0, 1, 0, 2, 0, 0, 1, 0, 0, 0, 0, 1]}
        self.assertEqual(pose_xy(third), (1.0, 2.0))
        self.assertAlmostEqual(path_length([first, second, third]), 3.0)


if __name__ == "__main__":
    unittest.main()
