"""Synthesize a sectioned, retryable Chinese narration for the challenge video."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

try:
    from scripts.challenge_video_contract import (
        public_repo_path,
        scan_public_bundle,
        sha256,
    )
except ModuleNotFoundError:  # Direct ``python scripts/...`` invocation.
    from challenge_video_contract import public_repo_path, scan_public_bundle, sha256


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATES = [
    {"voice": "zh-CN-YunjianNeural", "rate": "-6%", "pitch": "-6Hz"},
    {"voice": "zh-CN-YunxiNeural", "rate": "-8%", "pitch": "-4Hz"},
    {"voice": "zh-CN-YunyangNeural", "rate": "-7%", "pitch": "-5Hz"},
]
AUDITION_COPY = (
    "让机器人真正听懂语言指令，关键不是剪出一条好看的轨迹，"
    "而是让动作、观察、训练和评测形成可以复核的闭环。"
    "接下来我们从真实操作开始，逐步查看数据、训练和模型结果。"
)


def load_narration(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("narration must be a JSON object")
    return data


def split_sections(source: dict[str, Any]) -> list[dict[str, str]]:
    sections = source.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("narration sections must be a non-empty list")
    result: list[dict[str, str]] = []
    for section in sections:
        if not isinstance(section, dict):
            raise ValueError("narration section must be an object")
        chapter_id = section.get("chapter_id")
        title = section.get("title")
        text = section.get("text")
        if not all(isinstance(value, str) and value.strip() for value in (chapter_id, title, text)):
            raise ValueError("each narration section requires chapter_id, title and text")
        result.append(
            {
                "chapter_id": chapter_id.strip(),
                "title": title.strip(),
                "text": text.strip(),
            }
        )
    return result


def _pause_for_ending(text: str) -> int:
    stripped = text.rstrip()
    if not stripped:
        return 0
    if stripped.endswith(("。", "！", "？", ".", "!", "?")):
        return 320
    if stripped.endswith(("；", ";")):
        return 220
    if stripped.endswith(("，", "、", "：", ",", ":")):
        return 140
    return 180


def pause_schedule(text: str) -> list[int]:
    units = re.findall(r".*?[。！？；.!?;](?=.|$)", text)
    consumed = "".join(units)
    if consumed != text and text[len(consumed) :].strip():
        units.append(text[len(consumed) :])
    return [_pause_for_ending(unit) for unit in units if unit]


def _split_oversized_unit(unit: str, max_chars: int) -> list[str]:
    if len(unit) <= max_chars:
        return [unit]
    parts = re.findall(r".*?[，、：,:](?=.|$)", unit)
    consumed = "".join(parts)
    if consumed != unit:
        parts.append(unit[len(consumed) :])
    result: list[str] = []
    current = ""
    for part in parts:
        if len(part) > max_chars:
            if current:
                result.append(current)
                current = ""
            result.extend(
                part[index : index + max_chars]
                for index in range(0, len(part), max_chars)
            )
        elif len(current) + len(part) <= max_chars:
            current += part
        else:
            if current:
                result.append(current)
            current = part
    if current:
        result.append(current)
    return result


def split_text_chunks(text: str, max_chars: int = 260) -> list[dict[str, Any]]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    units = re.findall(r".*?[。！？；.!?;](?=.|$)", text)
    consumed = "".join(units)
    if consumed != text:
        units.append(text[len(consumed) :])
    chunks: list[dict[str, Any]] = []
    for unit in units:
        for part in _split_oversized_unit(unit, max_chars):
            if part:
                chunks.append({"text": part, "pause_ms": _pause_for_ending(part)})
    if "".join(chunk["text"] for chunk in chunks) != text:
        raise ValueError("narration chunking changed the source text")
    return chunks


def choose_voice(
    candidates: list[dict[str, str]],
    available_names: set[str],
) -> dict[str, str]:
    for index, candidate in enumerate(candidates):
        if candidate.get("voice") in available_names:
            selected = dict(candidate)
            selected["selection"] = "preferred" if index == 0 else "fallback"
            return selected
    raise ValueError("none of the configured Mandarin male voices is available")


def probe_audio_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def validate_audio(
    path: Path,
    probe: Callable[[Path], float] = probe_audio_duration,
) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        return probe(path) > 0.05
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, json.JSONDecodeError):
        return False


def run_with_retries(
    operation: Callable[[], None],
    output: Path,
    *,
    validator: Callable[[Path], bool] = validate_audio,
    attempts: int = 3,
) -> None:
    if attempts < 1:
        raise ValueError("attempts must be positive")
    last_error: Exception | None = None
    for _attempt in range(1, attempts + 1):
        output.unlink(missing_ok=True)
        try:
            operation()
            if validator(output):
                return
            last_error = RuntimeError("generated audio did not pass validation")
        except Exception as exc:  # Retried at this system boundary.
            last_error = exc
    raise RuntimeError(f"audio synthesis failed after {attempts} attempts") from last_error


async def _available_voices() -> list[dict[str, Any]]:
    import edge_tts

    return await edge_tts.list_voices()


async def _synthesize(
    text: str,
    output: Path,
    selected: dict[str, str],
) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(
        text=text,
        voice=selected["voice"],
        rate=selected["rate"],
        pitch=selected["pitch"],
        volume="+0%",
    )
    await communicate.save(str(output))


def available_voice_names() -> set[str]:
    voices = asyncio.run(_available_voices())
    return {
        str(voice.get("ShortName"))
        for voice in voices
        if voice.get("ShortName") and voice.get("Locale") == "zh-CN"
    }


def synthesize_file(text: str, output: Path, selected: dict[str, str]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    def operation() -> None:
        asyncio.run(_synthesize(text, output, selected))

    run_with_retries(operation, output, attempts=3)


def _run_ffmpeg(arguments: list[str]) -> None:
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *arguments],
        check=True,
    )


def create_silence(duration_ms: int, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if validate_audio(output):
        return
    _run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=24000:cl=mono",
            "-t",
            f"{duration_ms / 1000:.3f}",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "64k",
            "-ar",
            "24000",
            "-ac",
            "1",
            str(output),
        ]
    )


def concat_audio(paths: Iterable[Path], output: Path) -> None:
    items = list(paths)
    if not items:
        raise ValueError("at least one audio input is required")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".txt",
        encoding="utf-8",
        dir=output.parent,
        delete=False,
    ) as handle:
        list_path = Path(handle.name)
        for path in items:
            escaped = path.resolve().as_posix().replace("'", "'\\''")
            handle.write(f"file '{escaped}'\n")
    try:
        _run_ffmpeg(
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_path),
                "-c:a",
                "libmp3lame",
                "-b:a",
                "128k",
                "-ar",
                "24000",
                "-ac",
                "1",
                str(output),
            ]
        )
    finally:
        list_path.unlink(missing_ok=True)
    if not validate_audio(output):
        raise RuntimeError(f"concatenated audio is invalid: {output.name}")


def build_voice_metadata(
    *,
    root: Path,
    narration_path: Path,
    selected: dict[str, str],
    section_outputs: list[tuple[str, Path]],
    audition_outputs: list[tuple[str, Path]],
    combined_output: Path,
    duration_probe: Callable[[Path], float] = probe_audio_duration,
) -> dict[str, Any]:
    sections = [
        {
            "chapter_id": chapter_id,
            "output": public_repo_path(path, root),
            "duration_s": duration_probe(path),
            "sha256": sha256(path),
        }
        for chapter_id, path in section_outputs
    ]
    auditions = [
        {
            "voice": voice,
            "output": public_repo_path(path, root),
            "duration_s": duration_probe(path),
            "sha256": sha256(path),
        }
        for voice, path in audition_outputs
    ]
    metadata = {
        "schema_version": "geniesim-streamvln-challenge-voice/v1",
        "provider": "edge-tts",
        "language": "zh-CN",
        "style": "自然沉稳男声",
        "voice": selected["voice"],
        "rate": selected["rate"],
        "pitch": selected["pitch"],
        "selection": selected.get("selection", "preferred"),
        "custom_ssml": False,
        "pause_method": "ffmpeg_silence_between_chunks",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "narration": public_repo_path(narration_path, root),
        "narration_sha256": sha256(narration_path),
        "section_count": len(sections),
        "sections": sections,
        "auditions": auditions,
        "output": public_repo_path(combined_output, root),
        "duration_s": duration_probe(combined_output),
        "sha256": sha256(combined_output),
    }
    hits = scan_public_bundle(metadata)
    if hits:
        raise ValueError("voice metadata contains unsafe public text:\n" + "\n".join(hits))
    return metadata


def _load_or_create_config(path: Path) -> dict[str, Any]:
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("voice config must be a JSON object")
        return data
    return {
        "schema_version": "geniesim-streamvln-challenge-voice-config/v1",
        "style": "自然沉稳男声",
        "candidates": DEFAULT_CANDIDATES,
        "selected": None,
        "chunk_max_characters": 260,
        "chapter_pause_ms": 900,
    }


def synthesize_package(
    *,
    root: Path,
    narration_path: Path,
    config_path: Path,
    audition_dir: Path,
    output_dir: Path,
    metadata_path: Path,
) -> dict[str, Any]:
    narration_source = load_narration(narration_path)
    sections = split_sections(narration_source)
    config = _load_or_create_config(config_path)
    candidates = config.get("candidates", DEFAULT_CANDIDATES)
    if not isinstance(candidates, list):
        raise ValueError("voice candidates must be a list")
    available = available_voice_names()
    selected = choose_voice(candidates, available)

    audition_outputs: list[tuple[str, Path]] = []
    for candidate in candidates:
        voice = candidate.get("voice")
        if not isinstance(voice, str) or voice not in available:
            continue
        audition = audition_dir / f"{voice}.mp3"
        synthesize_file(AUDITION_COPY, audition, candidate)
        audition_outputs.append((voice, audition))

    work_dir = output_dir / "chunks"
    silence_dir = output_dir / "silence"
    silence_paths: dict[int, Path] = {}
    for duration_ms in (140, 180, 220, 320, 900):
        path = silence_dir / f"silence-{duration_ms}ms.mp3"
        create_silence(duration_ms, path)
        silence_paths[duration_ms] = path

    section_outputs: list[tuple[str, Path]] = []
    combined_parts: list[Path] = []
    max_chars = int(config.get("chunk_max_characters", 260))
    for section in sections:
        chapter_id = section["chapter_id"]
        chunks = split_text_chunks(section["text"], max_chars=max_chars)
        chapter_parts: list[Path] = []
        for index, chunk in enumerate(chunks, start=1):
            chunk_path = work_dir / chapter_id / f"{index:03d}.mp3"
            synthesize_file(chunk["text"], chunk_path, selected)
            chapter_parts.extend([chunk_path, silence_paths[chunk["pause_ms"]]])
        chapter_output = output_dir / f"{chapter_id}.mp3"
        concat_audio(chapter_parts, chapter_output)
        section_outputs.append((chapter_id, chapter_output))
        combined_parts.extend([chapter_output, silence_paths[900]])

    combined_output = output_dir / "challenge-voice.mp3"
    concat_audio(combined_parts, combined_output)
    config["selected"] = selected
    config["available_candidates"] = [
        candidate["voice"]
        for candidate in candidates
        if candidate.get("voice") in available
    ]
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    metadata = build_voice_metadata(
        root=root,
        narration_path=narration_path,
        selected=selected,
        section_outputs=section_outputs,
        audition_outputs=audition_outputs,
        combined_output=combined_output,
    )
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--narration",
        type=Path,
        default=ROOT / "content/challenge-video/narration-sections.json",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "content/challenge-video/voice-config.json",
    )
    parser.add_argument(
        "--audition-dir",
        type=Path,
        default=ROOT / "assets/challenge-video/auditions",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "assets/challenge-video/audio",
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=ROOT / "content/challenge-video/voice-metadata.json",
    )
    args = parser.parse_args()
    metadata = synthesize_package(
        root=ROOT,
        narration_path=args.narration.resolve(),
        config_path=args.config.resolve(),
        audition_dir=args.audition_dir.resolve(),
        output_dir=args.output_dir.resolve(),
        metadata_path=args.metadata.resolve(),
    )
    print(
        json.dumps(
            {
                "voice": metadata["voice"],
                "selection": metadata["selection"],
                "section_count": metadata["section_count"],
                "duration_s": metadata["duration_s"],
                "output": metadata["output"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
