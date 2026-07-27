"""Render the evidence-first GenieSim × StreamVLN challenge video."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont

try:
    from scripts.challenge_video_contract import (
        public_repo_path,
        scan_public_bundle,
        sha256,
    )
except ModuleNotFoundError:  # Direct ``python scripts/...`` invocation.
    from challenge_video_contract import public_repo_path, scan_public_bundle, sha256


ROOT = Path(__file__).resolve().parents[1]
FPS = 30
WIDTH = 1920
HEIGHT = 1080
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm"}
CHAPTER_TITLES = {
    "hook": "挑战从机器人动起来以后开始",
    "baseline": "定义一条可复核的闭环",
    "operation": "真实操作与安全门",
    "data": "数据采集与结构",
    "training": "LoRA 训练过程",
    "paired_eval": "Base / LoRA 配对评测",
    "innovation": "四类创新挑战",
    "closing": "把失败变成可复用资产",
}


def dimensions() -> tuple[int, int]:
    return WIDTH, HEIGHT


def public_label(source_type: str) -> str:
    labels = {
        "real_recording": "真实录屏",
        "real_evidence": "真实结果",
        "metric_animation": "真实结果",
        "diagram": "流程示意",
    }
    try:
        return labels[source_type]
    except KeyError as exc:
        raise ValueError(f"unsupported source type: {source_type}") from exc


def should_mask_existing_header(segment: dict[str, Any]) -> bool:
    if segment.get("source_type") != "real_recording":
        return True
    source = str(segment.get("source", ""))
    return any(
        marker in source
        for marker in (
            "/recapture/raw/stage0-",
            "/recapture/raw/stage1-",
            "/recapture/raw/stage2-",
        )
    )


def wrap_subtitle(text: str, limit: int = 16) -> list[str]:
    if limit <= 0:
        raise ValueError("subtitle limit must be positive")
    clean = "".join(text.strip().splitlines())
    return [clean[index : index + limit] for index in range(0, len(clean), limit)] or [""]


def _subtitle_lines(segment: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for item in segment.get("subtitle", []):
        lines.extend(wrap_subtitle(str(item), 16))
    return [line for line in lines if line][:2]


def source_window(segment: dict[str, Any]) -> tuple[float, float]:
    start = float(segment.get("source_in_s", 0))
    end = float(segment.get("source_out_s", 0))
    if start < 0 or end <= start:
        raise ValueError("source window must have 0 <= start < end")
    return start, end


def segment_cache_name(segment: dict[str, Any]) -> str:
    payload = json.dumps(
        segment,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()[:16]
    return f"{segment['segment_id']}-{digest}.mp4"


def transition_duration(previous_chapter: str | None, chapter: str) -> float:
    if previous_chapter is None or previous_chapter == chapter:
        return 0
    return 0.4


def video_input_args(source: Path, segment: dict[str, Any]) -> list[str]:
    start, end = source_window(segment)
    duration = end - start
    if segment.get("allow_loop"):
        return [
            "-stream_loop",
            "-1",
            "-ss",
            f"{start:.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(source),
        ]
    return [
        "-ss",
        f"{start:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(source),
    ]


def video_filter(segment: dict[str, Any], *, is_video: bool) -> str:
    if is_video:
        return (
            f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=#080e17,"
            f"fps={FPS},setsar=1"
        )
    frames = max(1, int(round(float(segment["duration_s"]) * FPS)))
    return (
        "scale=2000:1125:force_original_aspect_ratio=increase,"
        "crop=2000:1125,"
        f"zoompan=z='min(zoom+0.00045,1.04)':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:"
        f"s={WIDTH}x{HEIGHT}:fps={FPS},"
        f"fps={FPS},setsar=1"
    )


def video_encode_args(profile: str) -> list[str]:
    if profile == "videotoolbox":
        return [
            "-c:v",
            "h264_videotoolbox",
            "-b:v",
            "6000k",
            "-maxrate",
            "8000k",
            "-bufsize",
            "12000k",
            "-allow_sw",
            "1",
        ]
    if profile == "libx264":
        return ["-c:v", "libx264", "-preset", "medium", "-crf", "19"]
    raise ValueError(f"unsupported encoder profile: {profile}")


def audio_filter(duration_s: float, has_music: bool) -> str:
    duration = f"{duration_s:.3f}"
    if has_music:
        return (
            "[1:a]loudnorm=I=-16:TP=-1.0:LRA=11,"
            f"apad=whole_dur={duration}[voice];"
            "[2:a]volume=0.28[bg];"
            "[voice][bg]amix=inputs=2:duration=longest:dropout_transition=2,"
            "loudnorm=I=-16:TP=-1.0:LRA=11,"
            f"apad=whole_dur={duration}[a]"
        )
    return (
        "[1:a]loudnorm=I=-16:TP=-1.0:LRA=11,"
        f"apad=whole_dur={duration}[a]"
    )


def _font(size: int) -> ImageFont.ImageFont:
    candidates = (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    for candidate in candidates:
        path = Path(candidate)
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                pass
    return ImageFont.load_default()


def overlay_image(segment: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGBA", dimensions(), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    label = public_label(segment["source_type"])
    chapter = CHAPTER_TITLES.get(segment["chapter_id"], segment["chapter_id"])
    accent = (245, 174, 80, 255) if label in {"真实录屏", "真实结果"} else (77, 204, 238, 255)
    panel = (8, 18, 30, 218)
    white = (246, 249, 255, 255)
    muted = (198, 211, 228, 255)

    label_font = _font(28)
    chapter_font = _font(24)
    overlay_font = _font(31)
    subtitle_font = _font(29)

    if should_mask_existing_header(segment):
        draw.rectangle((0, 0, WIDTH, 148), fill=(8, 18, 30, 255))
        header = str(segment.get("overlay", "")).strip()
        header_text = header if len(header) <= 34 else header[:33] + "…"
        draw.text((42, 51), header_text, font=overlay_font, fill=white)

    label_box = (1360, 36, 1875, 119)
    draw.rounded_rectangle(label_box, radius=18, fill=panel)
    draw.text((1390, 53), label, font=label_font, fill=accent)
    chapter_width = draw.textlength(chapter, font=chapter_font)
    draw.text((1848 - chapter_width, 60), chapter, font=chapter_font, fill=muted)

    subtitle_lines = _subtitle_lines(segment)
    overlay = str(segment.get("overlay", "")).strip()
    panel_height = 84 + 44 * max(1, len(subtitle_lines))
    panel_box = (38, HEIGHT - panel_height - 28, 1240, HEIGHT - 28)
    draw.rounded_rectangle(panel_box, radius=20, fill=panel)
    overlay_text = overlay if len(overlay) <= 32 else overlay[:31] + "…"
    draw.text((68, panel_box[1] + 18), overlay_text, font=overlay_font, fill=white)
    y = panel_box[1] + 61
    for line in subtitle_lines:
        draw.text((68, y), line, font=subtitle_font, fill=muted)
        y += 40
    canvas.save(output)


def _run_ffmpeg(arguments: list[str]) -> None:
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *arguments],
        check=True,
    )


def _probe_duration(path: Path) -> float:
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


def _cache_valid(path: Path, expected_duration: float) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        return abs(_probe_duration(path) - expected_duration) <= 0.08
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, json.JSONDecodeError):
        return False


def render_segment(
    segment: dict[str, Any],
    *,
    root: Path,
    output: Path,
    overlay: Path,
    encoder_profile: str,
    fade_in_s: float = 0,
    fade_out_s: float = 0,
) -> None:
    duration = float(segment["duration_s"])
    if _cache_valid(output, duration):
        return
    source = (root / segment["source"]).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    is_video = source.suffix.lower() in VIDEO_SUFFIXES
    if is_video:
        inputs = video_input_args(source, segment)
    else:
        inputs = ["-loop", "1", "-t", f"{duration:.3f}", "-i", str(source)]
    filters = video_filter(segment, is_video=is_video)
    if fade_in_s > 0:
        filters += f",fade=t=in:st=0:d={fade_in_s:.3f}"
    if fade_out_s > 0 and duration > fade_out_s:
        filters += f",fade=t=out:st={duration - fade_out_s:.3f}:d={fade_out_s:.3f}"
    filter_complex = (
        f"[0:v]{filters}[base];"
        "[base][1:v]overlay=0:0:format=auto,format=yuv420p[v]"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    _run_ffmpeg(
        [
            *inputs,
            "-loop",
            "1",
            "-i",
            str(overlay),
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-t",
            f"{duration:.3f}",
            "-r",
            str(FPS),
            "-an",
            *video_encode_args(encoder_profile),
            "-movflags",
            "+faststart",
            str(output),
        ]
    )


def _srt_time(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds_value, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{seconds_value:02},{milliseconds:03}"


def write_srt(manifest: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    now = 0.0
    blocks: list[str] = []
    for index, segment in enumerate(manifest["segments"], start=1):
        duration = float(segment["duration_s"])
        lines = _subtitle_lines(segment)
        blocks.append(
            f"{index}\n{_srt_time(now)} --> {_srt_time(now + duration)}\n"
            + "\n".join(lines)
        )
        now += duration
    output.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def _trim_manifest(manifest: dict[str, Any], duration_s: float | None) -> dict[str, Any]:
    if duration_s is None:
        return copy.deepcopy(manifest)
    if duration_s <= 0:
        raise ValueError("render duration must be positive")
    selected: list[dict[str, Any]] = []
    remaining = duration_s
    for source_segment in manifest["segments"]:
        if remaining <= 0.001:
            break
        segment = copy.deepcopy(source_segment)
        take = min(float(segment["duration_s"]), remaining)
        if take < float(segment["duration_s"]):
            segment["duration_s"] = take
            segment["source_out_s"] = float(segment["source_in_s"]) + take
        selected.append(segment)
        remaining -= take
    if remaining > 0.02:
        raise ValueError("requested duration exceeds storyboard")
    trimmed = copy.deepcopy(manifest)
    trimmed["segments"] = selected
    trimmed["duration_s"] = duration_s
    return trimmed


def _concat_segments(paths: Iterable[Path], output: Path) -> None:
    items = list(paths)
    if not items:
        raise ValueError("no rendered segments")
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
                "-an",
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(output),
            ]
        )
    finally:
        list_path.unlink(missing_ok=True)


def _mux_audio(
    video: Path,
    voice: Path,
    music: Path | None,
    output: Path,
    duration_s: float,
) -> None:
    inputs = ["-i", str(video), "-i", str(voice)]
    if music is not None:
        inputs += ["-i", str(music)]
    _run_ffmpeg(
        [
            *inputs,
            "-filter_complex",
            audio_filter(duration_s, music is not None),
            "-map",
            "0:v",
            "-map",
            "[a]",
            "-t",
            f"{duration_s:.3f}",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )


def _real_ratio(segments: list[dict[str, Any]]) -> float:
    total = sum(float(segment["duration_s"]) for segment in segments)
    real = sum(
        float(segment["duration_s"])
        for segment in segments
        if segment["source_type"] == "real_recording"
    )
    return real / total if total else 0


def render_video(
    *,
    manifest_path: Path,
    voice: Path,
    output: Path,
    srt: Path,
    metadata_path: Path,
    work_dir: Path,
    music: Path | None,
    music_metadata: Path | None,
    encoder_profile: str,
    duration_s: float | None,
) -> dict[str, Any]:
    project_root = manifest_path.parent.parent.parent.resolve()
    source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    public_hits = scan_public_bundle(source_manifest)
    if public_hits:
        raise ValueError("unsafe public storyboard:\n" + "\n".join(public_hits))
    manifest = _trim_manifest(source_manifest, duration_s)
    actual_duration = sum(float(segment["duration_s"]) for segment in manifest["segments"])
    write_srt(manifest, srt)

    profile_dir = work_dir / encoder_profile
    overlays_dir = work_dir / "overlays"
    rendered: list[Path] = []
    previous_chapter: str | None = None
    for index, segment in enumerate(manifest["segments"]):
        current_chapter = segment["chapter_id"]
        next_chapter = (
            manifest["segments"][index + 1]["chapter_id"]
            if index + 1 < len(manifest["segments"])
            else None
        )
        fade_in = transition_duration(previous_chapter, current_chapter)
        fade_out = 0.4 if next_chapter is not None and next_chapter != current_chapter else 0
        clip = profile_dir / segment_cache_name(segment)
        overlay = overlays_dir / f"{segment['segment_id']}.png"
        overlay_image(segment, overlay)
        render_segment(
            segment,
            root=project_root,
            output=clip,
            overlay=overlay,
            encoder_profile=encoder_profile,
            fade_in_s=fade_in,
            fade_out_s=fade_out,
        )
        rendered.append(clip)
        previous_chapter = current_chapter

    silent = work_dir / f"{output.stem}-{int(round(actual_duration))}-silent.mp4"
    _concat_segments(rendered, silent)
    output.parent.mkdir(parents=True, exist_ok=True)
    _mux_audio(silent, voice, music, output, actual_duration)

    bgm: dict[str, Any] | None = None
    if music is not None:
        bgm = {
            "file": public_repo_path(music, project_root),
            "sha256": sha256(music),
        }
        if music_metadata is not None:
            provenance = json.loads(music_metadata.read_text(encoding="utf-8"))
            bgm["provenance"] = public_repo_path(music_metadata, project_root)
            bgm["provenance_sha256"] = sha256(music_metadata)
            bgm["license"] = provenance.get("license")
            if provenance.get("sha256") != bgm["sha256"]:
                raise ValueError("BGM provenance hash does not match audio")

    metadata = {
        "schema_version": "geniesim-streamvln-challenge-media/v1",
        "storyboard": public_repo_path(manifest_path, project_root),
        "output": public_repo_path(output, project_root),
        "output_sha256": sha256(output),
        "srt": public_repo_path(srt, project_root),
        "srt_sha256": sha256(srt),
        "voice": public_repo_path(voice, project_root),
        "voice_sha256": sha256(voice),
        "music": bgm,
        "duration_s": actual_duration,
        "width": WIDTH,
        "height": HEIGHT,
        "fps": FPS,
        "video_codec": "h264",
        "audio_codec": "aac",
        "audio_sample_rate": 48000,
        "audio_channels": 2,
        "encoder_profile": encoder_profile,
        "real_recording_ratio": _real_ratio(manifest["segments"]),
        "segment_count": len(manifest["segments"]),
        "paired_episode_ids": source_manifest["paired_episode_ids"],
        "paired_replays": source_manifest["paired_replays"],
        "facts": source_manifest["facts"],
    }
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "content/challenge-video/challenge-manifest.json",
    )
    parser.add_argument(
        "--voice",
        type=Path,
        default=ROOT / "assets/challenge-video/audio/challenge-voice.mp3",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--srt", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=ROOT / "assets/challenge-video/work",
    )
    parser.add_argument(
        "--music",
        type=Path,
        default=ROOT / "assets/series/ambient-original.wav",
    )
    parser.add_argument(
        "--music-metadata",
        type=Path,
        default=ROOT / "assets/series/ambient-original.json",
    )
    parser.add_argument("--no-music", action="store_true")
    parser.add_argument("--duration", type=float)
    parser.add_argument(
        "--encoder-profile",
        choices=("videotoolbox", "libx264"),
        default="videotoolbox",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    srt = args.srt.resolve() if args.srt else output.with_suffix(".srt")
    metadata_path = (
        args.metadata.resolve()
        if args.metadata
        else output.with_name(f"{output.stem}-media-manifest.json")
    )
    metadata = render_video(
        manifest_path=args.manifest.resolve(),
        voice=args.voice.resolve(),
        output=output,
        srt=srt,
        metadata_path=metadata_path,
        work_dir=args.work_dir.resolve(),
        music=None if args.no_music else args.music.resolve(),
        music_metadata=None if args.no_music else args.music_metadata.resolve(),
        encoder_profile=args.encoder_profile,
        duration_s=args.duration,
    )
    print(
        json.dumps(
            {
                "output": metadata["output"],
                "duration_s": metadata["duration_s"],
                "real_recording_ratio": metadata["real_recording_ratio"],
                "segment_count": metadata["segment_count"],
                "encoder_profile": metadata["encoder_profile"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
