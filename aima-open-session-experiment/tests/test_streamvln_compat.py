"""Contract tests for the pinned upstream compatibility overlay."""
import importlib
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


def _isolated_checkout(source: Path, target: Path, revision: str, cleanup) -> None:
    # Local clone transport traverses excluded blobs in shallow/promisor
    # sources. A detached worktree shares the genuine pinned Git objects but
    # has an independent HEAD/index and never invokes upload-pack.
    environment = {**os.environ, "GIT_NO_LAZY_FETCH": "1"}
    subprocess.run(["git", "-C", str(source), "worktree", "add", "--quiet", "--detach",
                    "--no-checkout", str(target), revision], check=True, env=environment)

    def remove_worktree():
        subprocess.run(["git", "-C", str(source), "worktree", "remove", "--force", str(target)],
                       check=True, text=True, capture_output=True, env=environment)

    # Register before any further setup can fail; only this test's directory
    # is removed, including its deliberately modified/untracked guard inputs.
    cleanup(remove_worktree)
    # `sparse-checkout set` enables worktree-specific sparse configuration.
    # Guard fixtures need Python source only, never excluded media payloads.
    subprocess.run(["git", "sparse-checkout", "set", "--no-cone", "/llava/**/*.py", "/streamvln/**/*.py"],
                   cwd=target, check=True, env=environment)
    subprocess.run(["git", "checkout", "--quiet", revision], cwd=target, check=True, env=environment)


class PartialCheckoutFixtureTests(unittest.TestCase):
    def test_shallow_partial_source_needs_no_excluded_blob_or_clone_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()

            def git(*arguments, cwd=source):
                return subprocess.run(["git", *arguments], cwd=cwd, check=True,
                                      text=True, capture_output=True).stdout.strip()

            git("init", "--quiet")
            git("config", "uploadpack.allowFilter", "true")
            for folder in ("llava", "streamvln", "assets"):
                (source / folder).mkdir()
            (source / "llava/__init__.py").write_text("# isolated source fixture\n")
            (source / "streamvln/__init__.py").write_text("# isolated source fixture\n")
            (source / "assets/excluded.bin").write_bytes(b"excluded media fixture\n")
            git("add", ".")
            git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                "commit", "--quiet", "-m", "partial checkout fixture")
            revision = git("rev-parse", "HEAD")
            excluded = git("rev-parse", "HEAD:assets/excluded.bin")
            partial = root / "partial"
            git("clone", "--quiet", "--filter=blob:none", "--depth=1", "--no-checkout",
                source.as_uri(), str(partial), cwd=root)
            git("sparse-checkout", "set", "llava", "streamvln", cwd=partial)
            git("checkout", "--quiet", revision, cwd=partial)
            self.assertEqual(git("rev-parse", "--is-shallow-repository", cwd=partial), "true")
            # Retain a real promisor checkout but make its fetch transport
            # unavailable. The selected source blobs are already local.
            git("remote", "set-url", "origin", (root / "unavailable").as_uri(), cwd=partial)

            def excluded_is_absent():
                result = subprocess.run(["git", "-C", str(partial), "cat-file", "-e", excluded],
                                        env={**os.environ, "GIT_NO_LAZY_FETCH": "1"},
                                        text=True, capture_output=True)
                self.assertNotEqual(result.returncode, 0)

            excluded_is_absent()
            original_sparse = git("sparse-checkout", "list", cwd=partial)
            original_status = git("status", "--porcelain", cwd=partial)
            target = root / "isolated"
            cleanups = []
            try:
                try:
                    _isolated_checkout(partial, target, revision, lambda *args: cleanups.append(args))
                except subprocess.CalledProcessError as exc:
                    self.fail(f"fixture creation fetched missing non-code objects: {exc}")
                self.assertEqual(git("rev-parse", "HEAD", cwd=target), revision)
                self.assertEqual((target / "llava/__init__.py").read_text(), "# isolated source fixture\n")
                (target / "llava/__init__.py").write_text("# isolated edit\n")
                self.assertEqual((partial / "llava/__init__.py").read_text(), "# isolated source fixture\n")
                self.assertFalse((target / "assets/excluded.bin").exists())
                excluded_is_absent()
                self.assertEqual(git("rev-parse", "HEAD", cwd=partial), revision)
                self.assertEqual(git("sparse-checkout", "list", cwd=partial), original_sparse)
                self.assertEqual(git("status", "--porcelain", cwd=partial), original_status)
            finally:
                for callback, *arguments in reversed(cleanups):
                    callback(*arguments)
            self.assertNotIn(str(target), git("worktree", "list", "--porcelain", cwd=partial))


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
        _isolated_checkout(Path(os.environ["STREAMVLN_REPO"]).resolve(), self.repo,
                           self.compat.UPSTREAM_REVISION, self.addCleanup)

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
