import tempfile
import unittest
from pathlib import Path

from adapter.stage2_preflight import _patch_qwen_tokenizer, build_command


class Stage2PreflightTests(unittest.TestCase):
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
                "if i != 0 and not tokenizer.legacy and IS_TOKENIZER_GREATER_THAN_0_14:",
                encoding="utf-8",
            )
            train.write_text(
                'tokenizer = transformers.AutoTokenizer.from_pretrained(model_args.model_name_or_path, '
                'cache_dir=training_args.cache_dir, model_max_length=training_args.model_max_length, '
                'padding_side="right")',
                encoding="utf-8",
            )
            self.assertEqual(_patch_qwen_tokenizer(repo)["status"], "applied")
            self.assertEqual(_patch_qwen_tokenizer(repo)["status"], "already_applied")
            self.assertIn("use_fast=False", train.read_text(encoding="utf-8"))
            self.assertIn("getattr(tokenizer", action_dataset.read_text(encoding="utf-8"))

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


if __name__ == "__main__":
    unittest.main()
