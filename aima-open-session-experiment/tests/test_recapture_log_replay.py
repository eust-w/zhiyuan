from __future__ import annotations

import unittest

from scripts.build_recapture_log_replay import (
    extract_reload_events,
    extract_single_batch_events,
    sanitize_public_log,
)


class RecaptureLogReplayTests(unittest.TestCase):
    def test_sanitize_public_log_removes_paths_accounts_and_network_addresses(self) -> None:
        raw = (
            "saved=/root/gpufree-data/private/model "
            "owner=user@example.com host=203.0.113.8 instanceID=abc-123"
        )

        sanitized = sanitize_public_log(raw)

        self.assertNotIn("/root/", sanitized)
        self.assertNotIn("user@example.com", sanitized)
        self.assertNotIn("203.0.113.8", sanitized)
        self.assertNotIn("abc-123", sanitized)
        self.assertIn("[已脱敏路径]", sanitized)

    def test_extract_single_batch_events_requires_and_keeps_measured_values(self) -> None:
        log = "\n".join(
            [
                "Trainable parameters: ~20.19 MB)",
                "len train_dataset  59",
                "{'loss': 0.4167, 'grad_norm': 0.3841767907142639}",
                "{'train_runtime': 2.7822, 'train_loss': 0.4167117476463318}",
                "Model saved to /root/private/output",
            ]
        )

        events = extract_single_batch_events(log)

        joined = "\n".join(events)
        self.assertIn("20.19 MB", joined)
        self.assertIn("59", joined)
        self.assertIn("loss=0.4167", joined)
        self.assertIn("grad_norm=0.3841767907142639", joined)
        self.assertIn("2.7822s", joined)
        self.assertNotIn("/root/", joined)

    def test_extract_reload_events_preserves_failure_then_verified_recovery(self) -> None:
        failure = "ModuleNotFoundError: No module named 'utils'"
        success = (
            "Loading checkpoint shards: 100%|##########| 4/4\n"
            '{"status": "passed", "peft_type": "LORA", '
            '"lora_r": 8, "trainable_parameters": 0}'
        )

        events = extract_reload_events(failure, success)

        self.assertIn("首次重载失败：缺少 utils 模块路径", events)
        self.assertIn("检查点分片加载：4/4", events)
        self.assertIn("重载状态：passed", events)
        self.assertIn("LoRA r=8", "\n".join(events))


if __name__ == "__main__":
    unittest.main()
