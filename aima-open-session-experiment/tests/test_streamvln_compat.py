"""Contract tests for the pinned upstream compatibility overlay."""
import importlib
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class CompatibilityApiTests(unittest.TestCase):
    def test_overlay_api_exists(self):
        self.assertIsNotNone(importlib.util.find_spec("adapter.streamvln_compat"))

    def test_missing_checkout_is_rejected(self):
        self.assertIsNotNone(importlib.util.find_spec("adapter.streamvln_compat"))
        compat = importlib.import_module("adapter.streamvln_compat")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                compat.prepare_checkout(Path(directory) / "missing")


@unittest.skipUnless(os.environ.get("STREAMVLN_REPO"), "set STREAMVLN_REPO to the pinned source checkout")
class PinnedOverlayTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("adapter.streamvln_compat"))
        self.compat = importlib.import_module("adapter.streamvln_compat")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name) / "upstream"
        subprocess.run(["git", "clone", "--quiet", "--shared", "--no-hardlinks", "--no-checkout", os.environ["STREAMVLN_REPO"], str(self.repo)], check=True)
        subprocess.run(["git", "sparse-checkout", "set", "llava", "streamvln"], cwd=self.repo, check=True)
        subprocess.run(["git", "checkout", "--quiet", self.compat.UPSTREAM_REVISION], cwd=self.repo, check=True)

    def test_known_source_is_patched_and_second_call_is_idempotent(self):
        first = self.compat.prepare_checkout(self.repo)
        self.assertEqual(first["status"], "ready")
        self.assertTrue(first["files"])
        self.assertTrue(all(item["changed"] for item in first["files"]))
        second = self.compat.prepare_checkout(self.repo)
        self.assertTrue(all(not item["changed"] for item in second["files"]))
        self.assertEqual([(item["path"], item["after_sha256"]) for item in first["files"]],
                         [(item["path"], item["after_sha256"]) for item in second["files"]])

    def test_unknown_target_source_is_rejected_before_any_write(self):
        victim = self.repo / "streamvln/dataset/vln_action_dataset.py"
        original = self.repo / "streamvln/streamvln_train.py"
        before = original.read_bytes()
        victim.write_text(victim.read_text() + "\n# unexpected edit\n")
        with self.assertRaisesRegex(ValueError, "source|content|modified"):
            self.compat.prepare_checkout(self.repo)
        self.assertEqual(original.read_bytes(), before)

    def test_modified_untargeted_import_is_rejected(self):
        victim = self.repo / "streamvln/utils/utils.py"
        victim.write_text(victim.read_text() + "\n# unexpected edit\n")
        with self.assertRaisesRegex(ValueError, "source|content|modified"):
            self.compat.prepare_checkout(self.repo)

    def test_unknown_revision_is_rejected(self):
        subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "--quiet", "--allow-empty", "-m", "fixture"], cwd=self.repo, check=True)
        with self.assertRaisesRegex(ValueError, "revision"):
            self.compat.prepare_checkout(self.repo)

    def test_untracked_python_shadow_module_is_rejected(self):
        (self.repo / "torch.py").write_text("raise RuntimeError('shadow')\n")
        with self.assertRaisesRegex(ValueError, "untracked|source"):
            self.compat.prepare_checkout(self.repo)

    def test_untracked_sourceless_bytecode_is_rejected(self):
        (self.repo / "torch.pyc").write_bytes(b"untrusted bytecode")
        with self.assertRaisesRegex(ValueError, "untracked|source"):
            self.compat.prepare_checkout(self.repo)

    def test_symlink_source_is_rejected_without_modifying_target(self):
        source = self.repo / "streamvln/streamvln_train.py"
        external = Path(self.temporary.name) / "external.py"
        external.write_bytes(source.read_bytes())
        before = external.read_bytes()
        source.unlink()
        source.symlink_to(external)
        with self.assertRaisesRegex(ValueError, "symlink|outside"):
            self.compat.prepare_checkout(self.repo)
        self.assertEqual(external.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
