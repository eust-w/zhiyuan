"""Render evidence-driven tutorial episodes from the shared series manifest."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

try:
    from scripts.series_manifest import load_manifest, metric_snapshot, validate_manifest
except ModuleNotFoundError:  # Direct `python scripts/build_series_media.py` invocation.
    from series_manifest import load_manifest, metric_snapshot, validate_manifest


ROOT = Path(__file__).resolve().parents[1]
FPS = 30
BG = (8, 14, 23, 255)
PANEL = (13, 25, 40, 232)
WHITE = (244, 248, 255, 255)
MUTED = (181, 198, 219, 255)
ORANGE = (245, 174, 80, 255)
CYAN = (77, 204, 238, 255)
PINK = (241, 104, 177, 255)


def episode_label(episode_id: str) -> str:
    return {
        "stage0": "阶段零",
        "stage1": "阶段一",
        "stage2": "阶段二",
        "stage3": "阶段三",
    }.get(episode_id, episode_id)


def dimensions(layout: str) -> tuple[int, int]:
    if layout == "landscape":
        return 1920, 1080
    if layout == "portrait":
        return 1080, 1920
    raise ValueError(f"unsupported layout: {layout}")


def public_path(path: Path, root: Path = ROOT) -> str:
    """Return a repository-relative path for shareable media metadata."""
    return path.resolve().relative_to(root.resolve()).as_posix()


def font(size: int):
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue
    return ImageFont.load_default()


def wrap_subtitle(text: str, limit: int = 16) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text.strip():
        if len(current) >= limit:
            if current.strip():
                lines.append(current.strip())
            current = ""
        current += char
    if current:
        if current.strip():
            lines.append(current.strip())
    return lines or [""]


def real_recording_ratio(episode: dict[str, Any]) -> float:
    total = sum(float(segment.get("duration_s", 0)) for segment in episode.get("segments", []))
    # The series requirement is about real *recorded footage*. A screenshot or
    # a plot is real evidence, but it must not inflate the video-footage ratio.
    real = sum(
        float(segment.get("duration_s", 0))
        for segment in episode.get("segments", [])
        if segment.get("source_type") == "real_recording"
    )
    return real / total if total else 0.0


def srt_time(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def write_srt(episode: dict[str, Any], path: Path) -> None:
    now = 0.0
    blocks: list[str] = []
    counter = 1
    for segment in episode["segments"]:
        duration = float(segment["duration_s"])
        subtitle = "\n".join(wrap_subtitle(" ".join(segment["subtitle"])))
        blocks.append(f"{counter}\n{srt_time(now)} --> {srt_time(now + duration)}\n{subtitle}\n")
        counter += 1
        now += duration
    path.write_text("\n".join(blocks), encoding="utf-8")


def overlay_image(episode: dict[str, Any], segment: dict[str, Any], path: Path, layout: str = "landscape") -> None:
    width, height = dimensions(layout)
    canvas = Image.new("RGBA", (width, height), (8, 14, 23, 0))
    if segment.get("preserve_source_overlay"):
        canvas.save(path)
        return
    draw = ImageDraw.Draw(canvas)
    scale = min(width / 1920, height / 1080)
    label_font = font(max(22, int(28 * scale)))
    title_font = font(max(27, int(34 * scale)))
    body_font = font(max(22, int(27 * scale)))
    source_type = segment["source_type"]
    label = {
        "real_recording": "真实录屏",
        "real_evidence": "真实结果图",
        "ai_diagram": "AI 示意图",
        "metric_animation": "真实指标图",
        "title_card": "章节卡",
    }[source_type]
    accent = ORANGE if source_type in {"real_recording", "real_evidence"} else CYAN
    margin = 32 if layout == "portrait" else 48
    top_h = 72 if layout == "portrait" else 75
    left_w = width - 2 * margin
    draw.rounded_rectangle((margin, 40, min(width - margin, margin + int(width * 0.55)), 40 + top_h), radius=18, fill=PANEL)
    draw.text((margin + 22, 62), f"{episode_label(episode['episode'])}  ·  {segment['segment_id']}", fill=accent, font=label_font)
    draw.rounded_rectangle((width - int(width * 0.34), 40, width - margin, 40 + top_h), radius=18, fill=PANEL)
    bbox = draw.textbbox((0, 0), label, font=label_font)
    draw.text((width - int(width * 0.17) - (bbox[2] - bbox[0]) // 2, 62), label, fill=accent, font=label_font)
    panel_top = height - (420 if layout == "portrait" else 250)
    draw.rounded_rectangle((margin, panel_top, width - margin, height - margin), radius=24, fill=PANEL)
    draw.text((margin + 34, panel_top + 28), segment.get("overlay", ""), fill=WHITE, font=title_font)
    narration = segment.get("narration", "")
    lines = wrap_subtitle(narration, 28 if layout == "portrait" else 40)
    y = panel_top + (120 if layout == "portrait" else 90)
    for line in lines[:2]:
        draw.text((margin + 34, y), line, fill=MUTED, font=body_font)
        y += 42 if layout == "portrait" else 38
    canvas.save(path)


def run_ffmpeg(args: list[str]) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def video_encode_args(profile: str = "libx264") -> list[str]:
    if profile == "videotoolbox":
        return [
            "-c:v", "h264_videotoolbox", "-b:v", "3500k", "-maxrate", "4500k",
            "-bufsize", "7000k", "-allow_sw", "1",
        ]
    if profile == "libx264":
        return ["-c:v", "libx264", "-preset", "medium", "-crf", "20"]
    raise ValueError(f"unsupported encoder profile: {profile}")


def render_segment(segment: dict[str, Any], root: Path, output: Path, overlay: Path, layout: str = "landscape", encoder_profile: str = "libx264") -> None:
    width, height = dimensions(layout)
    source = (root / segment["source"]).resolve()
    duration = float(segment["duration_s"])
    is_video = source.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}
    if is_video:
        input_args = ["-stream_loop", "-1", "-i", str(source)]
        if layout == "portrait":
            video_filter = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps={FPS}"
        else:
            video_filter = (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=#080e17,fps={FPS}"
            )
    else:
        input_args = ["-loop", "1", "-i", str(source)]
        crop_w = width + (128 if layout == "landscape" else 64)
        crop_h = height + (72 if layout == "landscape" else 64)
        video_filter = (
            f"scale={crop_w}:{crop_h}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}:x='min(max((iw-ow)*t/{duration:.3f},0),iw-ow)':y='(ih-oh)/2',fps={FPS}"
        )
    filter_complex = f"[0:v]{video_filter}[base];[base][1:v]overlay=0:0:format=auto,format=yuv420p[v]"
    run_ffmpeg(
        [
            *input_args,
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


def concat_segments(paths: list[Path], output: Path, duration: float | None) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8", delete=False) as handle:
        list_path = Path(handle.name)
        for path in paths:
            handle.write(f"file '{path.as_posix()}'\n")
    args = ["-f", "concat", "-safe", "0", "-i", str(list_path)]
    if duration is not None:
        args += ["-t", f"{duration:.3f}"]
    args += ["-an", "-c", "copy", "-movflags", "+faststart", str(output)]
    try:
        run_ffmpeg(args)
    finally:
        list_path.unlink(missing_ok=True)


def mux_audio(video: Path, output: Path, voice: Path | None, music: Path | None) -> None:
    if voice is None and music is None:
        shutil.copy2(video, output)
        return
    inputs = ["-i", str(video)]
    if voice:
        inputs += ["-i", str(voice)]
    if music:
        inputs += ["-stream_loop", "-1", "-i", str(music)]
    if voice and music:
        audio = (
            "[1:a]loudnorm=I=-16:TP=-1.0:LRA=11[voice];"
            "[2:a]volume=0.12[bg];"
            "[voice][bg]amix=inputs=2:duration=first:dropout_transition=2,loudnorm=I=-16:TP=-1.0:LRA=11[a]"
        )
    elif voice:
        audio = "[1:a]loudnorm=I=-16:TP=-1.0:LRA=11[a]"
    else:
        audio = "[1:a]volume=0.12,loudnorm=I=-26:TP=-1.0:LRA=11[a]"
    run_ffmpeg(
        [
            *inputs,
            "-filter_complex",
            audio,
            "-map",
            "0:v",
            "-map",
            "[a]",
            "-shortest",
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


def render_episode(manifest_path: Path, episode_id: str, output_dir: Path, eval_path: Path, duration: float | None = None, voice: Path | None = None, music: Path | None = None, layout: str = "landscape", encoder_profile: str = "libx264") -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    errors = validate_manifest(manifest, manifest_path.parent.parent.parent)
    if errors:
        raise ValueError("invalid series manifest:\n" + "\n".join(errors))
    episode = next(item for item in manifest["episodes"] if item["episode"] == episode_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"aima-{episode_id}-") as temp:
        temp_dir = Path(temp)
        rendered: list[Path] = []
        for index, segment in enumerate(episode["segments"], start=1):
            overlay = temp_dir / f"overlay-{index:03d}.png"
            clip = temp_dir / f"segment-{index:03d}.mp4"
            overlay_image(episode, segment, overlay, layout)
            render_segment(segment, manifest_path.parent.parent.parent, clip, overlay, layout, encoder_profile)
            rendered.append(clip)
        silent = output_dir / f"{episode_id}-silent.mp4"
        concat_segments(rendered, silent, duration)
        final = output_dir / f"{episode_id}.mp4"
        mux_audio(silent, final, voice, music)
    srt = output_dir / f"{episode_id}.srt"
    write_srt(episode, srt)
    snapshot = metric_snapshot(eval_path)
    metadata = {
        "schema_version": "aima-vln-series-media/v1",
        "episode": episode_id,
        "layout": layout,
        "width": dimensions(layout)[0],
        "height": dimensions(layout)[1],
        "duration_s": duration or sum(float(segment["duration_s"]) for segment in episode["segments"]),
        "real_recording_ratio": real_recording_ratio(episode),
        "metric_source": public_path(eval_path),
        "metrics": snapshot,
        "outputs": [public_path(final), public_path(srt)],
    }
    (output_dir / f"{episode_id}-media-manifest.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "content/series/series-manifest.json")
    parser.add_argument("--episode", required=True, choices=["stage0", "stage1", "stage2", "stage3"])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--eval", type=Path, default=ROOT / "experiments/exp02-equivalent-v3/eval_result.json")
    parser.add_argument("--duration", type=float)
    parser.add_argument("--voice", type=Path)
    parser.add_argument("--music", type=Path)
    parser.add_argument("--layout", choices=["landscape", "portrait"], default="landscape")
    parser.add_argument("--encoder-profile", choices=["libx264", "videotoolbox"], default="libx264")
    args = parser.parse_args()
    result = render_episode(args.manifest.resolve(), args.episode, args.output_dir.resolve(), args.eval.resolve(), args.duration, args.voice, args.music, args.layout, args.encoder_profile)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
