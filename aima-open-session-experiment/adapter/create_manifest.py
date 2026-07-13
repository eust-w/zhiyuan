"""Create a reproducible run-manifest.json with artifact SHA-256 hashes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .manifest import build_manifest, sha256_file, write_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--artifact", action="append", default=[])
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    manifest: dict[str, Any] = build_manifest(
        run_id=args.run_id,
        stage=args.stage,
        sources={
            "geniesim_preinstalled_commit": "a04fe4f7fda0ec6e01ab652fa19094008312bf97",
            "geniesim_public_reference": "v3.0.3",
            "streamvln_commit": "e48f6ff7e9201d93aae003e8f64b04c00cec13bc",
            "streamvln_checkpoint": "7b0269ad28e7039a32627b950766c09b5a646f8e",
            "siglip": "9fdffc58afc957d1a03a25b10dba0329ab15c2a3",
        },
        config={"official": False, "scene": "market_00_g2", "target_id": "red-target-marker", "service": "127.0.0.1:5802"},
    )
    artifacts: dict[str, str] = {}
    for value in args.artifact:
        path = (root / value).resolve()
        if not path.is_file() or root not in path.parents:
            raise SystemExit(f"artifact must be a file under root: {value}")
        artifacts[str(path.relative_to(root))] = sha256_file(path)
    manifest["artifacts"] = artifacts
    write_manifest(args.output.expanduser().resolve(), manifest)
    print(json.dumps({"output": str(args.output), "artifacts": len(artifacts)}))


if __name__ == "__main__":
    main()
