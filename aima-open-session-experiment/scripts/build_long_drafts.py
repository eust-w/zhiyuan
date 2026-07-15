"""Create clearly watermarked long rough cuts from the 60s style samples.

These are not final tutorials: until fresh GPUFree footage is recovered, the
same checked-in sample is looped only to validate narration, audio, timing and
encoding. The watermark and metadata prevent the output from being mistaken
for the required 75% real-recording final cut.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]


def font(size: int):
    for path in ("/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/Hiragino Sans GB.ttc"):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def run(args: list[str]) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def srt_time(seconds: float) -> str:
    millis = int(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def write_rough_srt(path: Path, duration: float, episode: str) -> None:
    labels = [
        f"{episode.upper()} 粗剪草稿",
        "旧素材片段复用",
        "旁白与音频已合成",
        "真实补录仍待回收",
        "不作为最终发布",
    ]
    blocks: list[str] = []
    index = 1
    start = 0.0
    while start < duration:
        end = min(start + 30.0, duration)
        blocks.append(f"{index}\n{srt_time(start)} --> {srt_time(end)}\n{labels[(index - 1) % len(labels)]}\n")
        start = end
        index += 1
    path.write_text("\n".join(blocks), encoding="utf-8")


def watermark(path: Path) -> None:
    image = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((50, 45, 890, 125), radius=18, fill=(6, 16, 28, 225), outline=(245, 174, 80, 255), width=3)
    draw.text((76, 67), "粗剪草稿｜旧素材片段复用｜未满足最终比例", fill=(255, 226, 172, 255), font=font(30))
    image.save(path, format="PNG")


def write_draft(episode: str, output: Path) -> dict[str, object]:
    sample = ROOT / "assets/series/style-sample" / episode / f"{episode}.mp4"
    if episode == "stage0":
        sample = ROOT / "assets/series/style-sample/stage0.mp4"
    voice = ROOT / "assets/series" / episode / f"{episode}-voice.mp3"
    music = ROOT / "assets/series/ambient-original.wav"
    if not sample.is_file() or not voice.is_file() or not music.is_file():
        raise FileNotFoundError(f"missing rough-cut input for {episode}")
    output.mkdir(parents=True, exist_ok=True)
    overlay = output / f"{episode}-draft-watermark.png"
    watermark(overlay)
    watermarked_sample = output / f"{episode}-watermarked-sample.mp4"
    run([
        "-i", str(sample), "-i", str(overlay),
        "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto[v]",
        "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-r", "30", "-movflags", "+faststart", str(watermarked_sample),
    ])
    video = output / f"{episode}-rough-cut-draft.mp4"
    args = [
        "-stream_loop", "-1", "-i", str(watermarked_sample),
        "-i", str(voice),
        "-stream_loop", "-1", "-i", str(music),
        "-filter_complex",
        "[1:a]loudnorm=I=-16:TP=-1.0:LRA=11[voice];"
        "[2:a]volume=0.12[bg];"
        "[voice][bg]amix=inputs=2:duration=first:dropout_transition=2,loudnorm=I=-16:TP=-1.0:LRA=11[a]",
        "-map", "0:v", "-map", "[a]", "-shortest",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", str(video),
    ]
    run(args)
    duration = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)], text=True))
    srt = output / f"{episode}-rough-cut-draft.srt"
    write_rough_srt(srt, duration, episode)
    metadata = {
        "schema_version": "aima-vln-long-draft/v1",
        "episode": episode,
        "status": "rough_cut_draft",
        "duration_s": duration,
        "source_sample": str(sample.relative_to(ROOT)),
        "watermarked_sample": str(watermarked_sample.relative_to(ROOT)),
        "source_reuse": True,
        "real_recording_ratio_verified": False,
        "final_acceptance_blocker": "GPUFree fresh recordings unavailable; do not publish",
        "voice": str(voice.relative_to(ROOT)),
        "music": str(music.relative_to(ROOT)),
        "watermark": str(overlay.relative_to(ROOT)),
        "srt": str(srt.relative_to(ROOT)),
    }
    (output / f"{episode}-rough-cut-manifest.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", choices=["stage0", "stage1", "stage2", "stage3"], required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "assets/series/long-drafts")
    parser.add_argument("--srt-only", action="store_true")
    args = parser.parse_args()
    output = args.output_dir.resolve() / args.episode
    if args.srt_only:
        video = output / f"{args.episode}-rough-cut-draft.mp4"
        duration = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)], text=True))
        srt = output / f"{args.episode}-rough-cut-draft.srt"
        write_rough_srt(srt, duration, args.episode)
        print(str(srt))
    else:
        print(json.dumps(write_draft(args.episode, output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
