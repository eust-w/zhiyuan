"""Run manifest and artifact hashing helpers."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DISCLAIMER = "Reference implementation inspired by the AIMA workflow; not an official course integration."


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(*, run_id: str, stage: str, sources: Mapping[str, str], config: Mapping[str, Any]) -> dict[str, Any]:
    if not run_id.strip() or not stage.strip():
        raise ValueError("run_id and stage are required")
    return {
        "run_id": run_id,
        "stage": stage,
        "official": False,
        "disclaimer": DISCLAIMER,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "sources": dict(sources),
        "config": dict(config),
        "artifacts": {},
    }


def write_manifest(path: Path, manifest: Mapping[str, Any]) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temp_path = Path(handle.name)
    os.replace(temp_path, path)

