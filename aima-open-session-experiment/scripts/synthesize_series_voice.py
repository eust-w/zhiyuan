"""Synthesize the Chinese narration for one tutorial episode."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def public_voice_path(path: Path, root: Path = ROOT) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def load_narration(path: Path) -> str:
    text = "\n".join(line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    if len(text) < 500:
        raise ValueError(f"narration is too short for a long tutorial: {path}")
    return text


async def synthesize(text: str, output: Path, voice: str, rate: str) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
    await communicate.save(str(output))


def build_voice(narration: Path, output: Path, voice: str = "zh-CN-YunyangNeural", rate: str = "-8%") -> dict[str, object]:
    text = load_narration(narration)
    output.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(synthesize(text, output, voice, rate))
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    metadata = {
        "schema_version": "aima-vln-series-voice/v1",
        "narration": public_voice_path(narration),
        "output": public_voice_path(output),
        "voice": voice,
        "rate": rate,
        "language": "zh-CN",
        "style": "沉稳男声",
        "characters": len(text),
        "sha256": digest,
    }
    output.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--narration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--voice", default="zh-CN-YunyangNeural")
    parser.add_argument("--rate", default="-8%")
    args = parser.parse_args()
    print(json.dumps(build_voice(args.narration.resolve(), args.output.resolve(), args.voice, args.rate), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
