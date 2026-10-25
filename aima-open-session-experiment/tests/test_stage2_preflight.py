import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from adapter import stage2_preflight
from adapter.stage2_preflight import _patch_qwen_tokenizer, build_command


class Stage2PreflightTests(unittest.TestCase):
    def test_preflight_records_overlay_failure_without_training_or_legacy_patch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, vision = root / "base", root / "vision"
            base.mkdir()
            vision.mkdir()
            (base / "config.json").write_text(json.dumps({"mm_vision_tower": str(vision)}))
            (vision / "config.json").write_text("{}")
            for directory in (base, vision):
                (directory / "model.safetensors").write_bytes(b"format guard fixture")
            result = root / "result.json"
            argv = ["stage2", "--python", sys.executable, "--repo", str(root / "source"),
                    "--checkpoint", str(base), "--vision", str(vision),
                    "--dataset", str(root / "data"), "--output", str(root / "output"),
                    "--result", str(result), "--execute"]
            with patch.object(sys, "argv", argv), \
                    patch.object(stage2_preflight, "prepare_checkout", create=True,
                                 side_effect=ValueError("unreviewed checkout rejected")), \
                    patch.object(stage2_preflight, "_patch_qwen_tokenizer",
                                 side_effect=AssertionError("legacy patch must not execute")), \
                    patch.object(stage2_preflight.subprocess, "Popen",
                                 side_effect=AssertionError("blocked training must not execute")), \
                    contextlib.redirect_stdout(io.StringIO()):
                try:
                    stage2_preflight.main()
                except Exception as exc:
                    self.fail(f"preflight did not report a blocked overlay: {exc}")
            gates = json.loads(result.read_text())["gates"]
            self.assertEqual(gates["streamvln_compat"]["status"], "blocked")
            self.assertIn("unreviewed checkout", gates["streamvln_compat"]["error"])
            self.assertEqual(gates["full_training"]["status"], "blocked")
            self.assertFalse((root / "base-qwen-compat").exists())

    def test_qwen_tokenizer_patch_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            source = repo / "streamvln"
            source.mkdir()
            train = source / "streamvln_train.py"
            dataset = source / "dataset"
            dataset.mkdir()
            action_dataset = dataset / "vln_action_dataset.py"
            action_dataset.write_text(
                "def preprocess_qwen():\n"
                "    im_start, im_end = tokenizer.additional_special_tokens_ids\n\n"
                "if i != 0 and not tokenizer.legacy and IS_TOKENIZER_GREATER_THAN_0_14:\n"
                "    if conversation_lib.default_conversation.sep_style == conversation_lib.SeparatorStyle.PLAIN:\n"
                "        return preprocess_plain(sources, tokenizer)\n"
                "    if conversation_lib.default_conversation.sep_style == conversation_lib.SeparatorStyle.LLAMA_2:\n"
                "        return preprocess_llama_2(sources, tokenizer, has_image=has_image)\n"
                "    if conversation_lib.default_conversation.version == \"qwen\":\n"
                "        return preprocess_qwen(sources, tokenizer, has_image=has_image)\n"
                "    if conversation_lib.default_conversation.version == \"gemma\":\n",
                encoding="utf-8",
            )
            train.write_text(
                'tokenizer = transformers.AutoTokenizer.from_pretrained(model_args.model_name_or_path, '
                'cache_dir=training_args.cache_dir, model_max_length=training_args.model_max_length, '
                'padding_side="right")\n\n\ndef preprocess_qwen():\n'
                '    im_start, im_end = tokenizer.additional_special_tokens_ids\n\n\ndef preprocess():\n'
                '    if conversation_lib.default_conversation.sep_style == conversation_lib.SeparatorStyle.PLAIN:\n'
                '        return preprocess_plain(sources, tokenizer)\n'
                '    if conversation_lib.default_conversation.sep_style == conversation_lib.SeparatorStyle.LLAMA_2:\n'
                '        return preprocess_llama_2(sources, tokenizer, has_image=has_image)\n\n\n'
                '    return model\n\n\ndef train(attn_implementation=None):\n\n        model.initialize_vision_tokenizer(model_args, tokenizer=tokenizer)\n',
                encoding="utf-8",
            )
            self.assertEqual(_patch_qwen_tokenizer(repo)["status"], "applied")
            self.assertEqual(_patch_qwen_tokenizer(repo)["status"], "already_applied")
            self.assertIn("use_fast=False", train.read_text(encoding="utf-8"))
            self.assertIn("lm_head.out_features", train.read_text(encoding="utf-8"))
            self.assertIn("initialize_vision_tokenizer", train.read_text(encoding="utf-8"))
            self.assertIn("getattr(tokenizer", action_dataset.read_text(encoding="utf-8"))
            self.assertIn('convert_tokens_to_ids("<|im_start|>")', train.read_text(encoding="utf-8"))
            self.assertIn('convert_tokens_to_ids("<|im_end|>")', action_dataset.read_text(encoding="utf-8"))
            self.assertLess(
                action_dataset.read_text(encoding="utf-8").index('version == "qwen"'),
                action_dataset.read_text(encoding="utf-8").index("SeparatorStyle.LLAMA_2"),
            )

    def test_command_keeps_qwen_model_family_path(self):
        command = build_command(
            python="python",
            repo=Path("/repo"),
            checkpoint=Path("/weights/StreamVLN-qwen-compat"),
            vision=Path("/vision"),
            data=Path("/data"),
            output=Path("/out"),
        )
        self.assertIn("/weights/StreamVLN-qwen-compat", command)
        version_index = command.index("--version")
        self.assertEqual(command[version_index + 1], "qwen_2")

    def test_command_can_limit_single_batch_gate(self):
        command = build_command(
            python="python", repo=Path("/repo"), checkpoint=Path("/qwen"), vision=Path("/vision"),
            data=Path("/data"), output=Path("/out"), max_steps=1,
        )
        self.assertEqual(command[-2:], ["--max_steps", "1"])


if __name__ == "__main__":
    unittest.main()
