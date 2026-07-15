"""Create a small original ambient bed and record its provenance.

The audio is synthesized locally from two sine oscillators. It is not a
downloaded recording, so the series does not depend on an unverified music
licence. The recipe and SHA-256 are written beside the file for review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def public_output_path(path: Path, root: Path = ROOT) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def build_bgm(output: Path, duration_s: float) -> dict[str, object]:
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=110:sample_rate=48000:duration={duration_s}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=164.81:sample_rate=48000:duration={duration_s}",
        "-filter_complex",
        "[0:a]volume=0.025[a0];[1:a]volume=0.015[a1];[a0][a1]amix=inputs=2:duration=longest,alimiter=limit=0.8[a]",
        "-map",
        "[a]",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-c:a",
        "pcm_s16le",
        str(output),
    ]
    subprocess.run(command, check=True)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    public_file = public_output_path(output)
    public_command = [public_file if item == str(output) else item for item in command]
    metadata = {
        "schema_version": "aima-vln-original-audio/v1",
        "kind": "original_synthesized_ambient",
        "file": public_file,
        "duration_s": duration_s,
        "sample_rate": 48000,
        "channels": 2,
        "license": "original local synthesis; no third-party recording",
        "recipe": "two low sine oscillators (110Hz, 164.81Hz), low-volume mix, limiter",
        "command": " ".join(public_command),
        "sha256": digest,
    }
    output.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=900.0)
    args = parser.parse_args()
    print(json.dumps(build_bgm(args.output.resolve(), args.duration), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
