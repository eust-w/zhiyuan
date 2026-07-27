import json
import tempfile
import unittest
from pathlib import Path

from scripts.challenge_video_contract import (
    APPROVED_CERTIFICATE_COPY,
    FORBIDDEN_PUBLIC_TERMS,
    evidence_snapshot,
    public_repo_path,
    scan_public_bundle,
    scan_public_text,
    scan_sensitive_text,
    sha256,
    validate_claims,
)


ROOT = Path(__file__).resolve().parents[1]


class ChallengeVideoContractTests(unittest.TestCase):
    def test_extracts_metrics_from_authoritative_json(self):
        facts = evidence_snapshot(ROOT)

        self.assertEqual(
            facts["heldout_episode_ids"],
            [f"eval-{seed}" for seed in range(2001, 2011)],
        )
        self.assertEqual(facts["scene"], "market_00_g2")
        self.assertEqual(facts["robot"], "G2_omnipicker")
        self.assertEqual(facts["dataset"]["train_episodes"], 50)
        self.assertEqual(facts["dataset"]["heldout_episodes"], 10)
        self.assertEqual(facts["base"]["success_0_5"], 0)
        self.assertEqual(facts["lora"]["success_0_5"], 0)
        self.assertEqual(facts["base"]["success_3"], 2)
        self.assertEqual(facts["lora"]["success_3"], 1)
        self.assertEqual(facts["base"]["collisions"], 132)
        self.assertEqual(facts["lora"]["collisions"], 45)
        self.assertEqual(
            facts["lora"]["mean_final_distance_to_goal"],
            4.686244300975281,
        )
        self.assertEqual(facts["lora_training"]["updates"], 59)
        self.assertEqual(facts["lora_training"]["loss_first"], 0.4167)
        self.assertEqual(facts["lora_training"]["loss_last"], 0.0823)
        self.assertAlmostEqual(facts["lora_training"]["peak_gpu_memory_gib"], 27.19, places=2)
        self.assertTrue(facts["lora_training"]["adapter_reload_passed"])

    def test_rejects_forbidden_public_wording(self):
        for term in FORBIDDEN_PUBLIC_TERMS:
            with self.subTest(term=term):
                self.assertEqual(scan_public_text(f"开头{term}结尾"), [term])

    def test_rejects_sensitive_values_and_absolute_paths(self):
        text = (
            "邮箱 a@example.com，服务 10.0.0.1，本地 /Users/name/work，"
            "远端 /root/work，命令 ssh user@host，账号密码 password: abc"
        )

        hits = scan_sensitive_text(text)

        self.assertGreaterEqual(len(hits), 6)

    def test_certificate_copy_is_conditional(self):
        self.assertEqual(
            validate_claims("完成后保证获得证书"),
            ["certificate claim must be conditional"],
        )
        self.assertEqual(validate_claims(APPROVED_CERTIFICATE_COPY), [])

    def test_public_bundle_reports_paths_to_bad_text(self):
        bundle = {
            "clean": "真实录屏",
            "nested": [{"copy": f"包含{FORBIDDEN_PUBLIC_TERMS[0]}字样"}],
        }

        self.assertEqual(
            scan_public_bundle(bundle),
            [f"$.nested[0].copy: forbidden:{FORBIDDEN_PUBLIC_TERMS[0]}"],
        )

    def test_paths_and_hashes_are_repository_relative_and_stable(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "artifact.txt"
            path.write_text("challenge", encoding="utf-8")

            relative = public_repo_path(path, ROOT)

            self.assertFalse(relative.startswith("/"))
            self.assertTrue(relative.endswith("/artifact.txt"))
            self.assertEqual(
                sha256(path),
                "2dd00bd77e0222ced882665481a9c1d9f907309d16e05ed007a1ea63928477a9",
            )

    def test_evidence_snapshot_rejects_unpaired_episode_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            exp = root / "experiments/exp02-equivalent-v3"
            exp.mkdir(parents=True)
            source_exp = ROOT / "experiments/exp02-equivalent-v3"
            for name in (
                "eval_result.json",
                "stage2_result_v2.json",
                "dataset-validation.json",
                "stage0-health.json",
            ):
                (exp / name).write_bytes((source_exp / name).read_bytes())
            data = json.loads((exp / "eval_result.json").read_text(encoding="utf-8"))
            data["lora_model"]["model_evaluation"]["episode_ids"][-1] = "eval-9999"
            (exp / "eval_result.json").write_text(
                json.dumps(data, ensure_ascii=False),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "ordered held-out episode IDs"):
                evidence_snapshot(root)


if __name__ == "__main__":
    unittest.main()
