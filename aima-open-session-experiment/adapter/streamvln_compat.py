"""Checked compatibility overlay for the pinned, scoped StreamVLN source.

The wrapper is original project code. The patch contains upstream modifications
under the applicable third-party terms; see THIRD_PARTY_NOTICES.md. This guard
does not sandbox Python or protect against concurrent filesystem tampering.
Use a trusted checkout that no other process edits while it is being loaded.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


UPSTREAM_REVISION = "e48f6ff7e9201d93aae003e8f64b04c00cec13bc"
PROFILE = "qwen-siglip-bf16-lora-v5"
ASSETS = Path(__file__).with_name("compat_assets")


def _git(repo: Path, *args: str, input_data: bytes | None = None) -> bytes:
    result = subprocess.run(["git", "--no-pager", "-C", str(repo), *args],
                            input=input_data, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise ValueError("StreamVLN source checkout validation failed: " + result.stderr.decode("utf-8", "replace").strip())
    return result.stdout


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source_path(repo: Path, relative: str) -> Path:
    path = repo / relative
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != repo and repo in parent.parents):
        raise ValueError(f"source symlink is not permitted: {relative}")
    if not path.resolve().is_relative_to(repo):
        raise ValueError(f"source path resolves outside checkout: {relative}")
    if not path.is_file():
        raise ValueError(f"required source file is absent: {relative}")
    return path


def prepare_checkout(repo: Path) -> dict[str, Any]:
    """Validate all scoped source before applying the deterministic overlay.

    Only a clean pinned source or this exact overlay is accepted. A mixture of
    original and fully patched files can be completed after an interrupted run.
    Unknown edits, unknown revisions, symlinks and untracked importable source
    are rejected before any write. The patch is checked in full before apply.
    """
    repo = Path(repo).expanduser().resolve()
    if not repo.is_dir():
        raise ValueError("StreamVLN source checkout must exist")
    revision = _git(repo, "rev-parse", "HEAD").decode().strip()
    if revision != UPSTREAM_REVISION:
        raise ValueError(f"unsupported StreamVLN revision: {revision}")
    manifest = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))
    patch = (ASSETS / "streamvln-v5.patch").read_bytes()
    if manifest["revision"] != revision or _digest(patch) != manifest["patch_sha256"]:
        raise ValueError("compatibility patch manifest/hash mismatch")
    targets = {item["path"]: item for item in manifest["files"]}
    tracked = _git(repo, "ls-tree", "-r", "--name-only", "-z", "HEAD").decode().split("\0")
    source_files = [name for name in tracked if name.endswith(".py") and name.startswith(("llava/", "streamvln/"))]
    untracked = _git(repo, "ls-files", "--others", "-z").decode().split("\0")
    for name in untracked:
        # Ordinary __pycache__ files are interpreter products, not standalone
        # modules. Top-level sourceless bytecode can shadow an imported module.
        sourceless = name.endswith((".pyc", ".pyo")) and "__pycache__" not in Path(name).parts
        if name.endswith((".py", ".so", ".pyd")) or sourceless:
            raise ValueError(f"untracked importable source is not permitted: {name}")
    reports = []
    pending = []
    for relative in source_files:
        path = _source_path(repo, relative)
        actual = _digest(path.read_bytes())
        original = _digest(_git(repo, "show", f"HEAD:{relative}"))
        item = targets.get(relative)
        if item is None:
            if actual != original:
                raise ValueError(f"unexpected modified source: {relative}")
            continue
        if item["before_sha256"] != original:
            raise ValueError(f"pinned source hash disagrees with patch: {relative}")
        if actual not in (item["before_sha256"], item["after_sha256"]):
            raise ValueError(f"unexpected modified source content: {relative}")
        changed = actual != item["after_sha256"]
        if changed:
            pending.append(relative)
        reports.append({**item, "changed": changed})
    if {item["path"] for item in reports} != set(targets):
        raise ValueError("patch targets are not all tracked scoped source")
    if pending:
        selectors = [f"--include={relative}" for relative in pending]
        _git(repo, "apply", "--check", *selectors, "-", input_data=patch)
        _git(repo, "apply", *selectors, "-", input_data=patch)
    for item in reports:
        if _digest(_source_path(repo, item["path"]).read_bytes()) != item["after_sha256"]:
            raise ValueError(f"post-apply source hash mismatch: {item['path']}")
    return {"status": "ready", "revision": revision, "profile": PROFILE,
            "patch_sha256": manifest["patch_sha256"], "files": reports}
