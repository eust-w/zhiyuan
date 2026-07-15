"""Render a sanitized, source-backed terminal replay for public tutorial media."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
WIDTH = 1920
HEIGHT = 1080
FPS = 30
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
IPV4 = re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)")
ABSOLUTE_PATH = re.compile(r"/(?:Users|root|home|opt|mnt|data|workspace|tmp)(?:/[^\s,'\"}\]]+)+")
INSTANCE_VALUE = re.compile(r"(?i)(instance\s*id|instanceID|实例ID)\s*[:=]\s*[^\s,}]+")


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ):
        path = Path(candidate)
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def sanitize_public_log(text: str) -> str:
    """Remove terminal control codes and public-content sensitive identifiers."""
    clean = ANSI.sub("", text).replace("\r", "\n")
    clean = ABSOLUTE_PATH.sub("[已脱敏路径]", clean)
    clean = EMAIL.sub("[已脱敏账号]", clean)
    clean = IPV4.sub("[已脱敏地址]", clean)
    clean = INSTANCE_VALUE.sub(lambda match: f"{match.group(1)}=[已脱敏实例]", clean)
    return clean


def _required(pattern: str, text: str, label: str) -> re.Match[str]:
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        raise ValueError(f"missing measured field: {label}")
    return match


def extract_single_batch_events(text: str) -> list[str]:
    """Extract the measured single-batch gate without copying remote paths."""
    clean = sanitize_public_log(text)
    trainable = _required(r"Trainable parameters:\s*~([0-9.]+\s*MB)", clean, "trainable parameters").group(1)
    dataset = _required(r"len train_dataset\s+(\d+)", clean, "dataset length").group(1)
    loss = _required(r"['\"]loss['\"]:\s*([0-9.]+)", clean, "loss").group(1)
    grad = _required(r"['\"]grad_norm['\"]:\s*([0-9.]+)", clean, "grad norm").group(1)
    runtime = _required(r"['\"]train_runtime['\"]:\s*([0-9.]+)", clean, "runtime").group(1)
    _required(r"Model saved to\s+\[已脱敏路径\]", clean, "saved model")
    return [
        "训练环境检查：独立 Python 环境与 BF16 配置已启动",
        f"可训练参数：{trainable}｜训练样本：{dataset}",
        "单批前后向：1/1 更新步完成",
        f"实测 loss={loss}｜grad_norm={grad}",
        f"实测 runtime={runtime}s｜模型输出已保存到脱敏目录",
    ]


def extract_reload_events(failure: str, success: str) -> list[str]:
    """Keep the honest failure-to-recovery sequence for adapter reload."""
    failure_clean = sanitize_public_log(failure)
    success_clean = sanitize_public_log(success)
    _required(r"ModuleNotFoundError:\s*No module named ['\"]utils['\"]", failure_clean, "reload failure")
    shards = _required(r"Loading checkpoint shards:.*?100%.*?(\d+)/(\d+)", success_clean, "checkpoint shards")
    status = _required(r"['\"]status['\"]:\s*['\"]([^'\"]+)", success_clean, "reload status").group(1)
    peft_type = _required(r"['\"]peft_type['\"]:\s*['\"]([^'\"]+)", success_clean, "peft type").group(1)
    lora_r = _required(r"['\"]lora_r['\"]:\s*(\d+)", success_clean, "lora rank").group(1)
    trainable = _required(r"['\"]trainable_parameters['\"]:\s*(\d+)", success_clean, "inference trainable parameters").group(1)
    return [
        "首次重载失败：缺少 utils 模块路径",
        "定位原因：新进程未包含两个公开 StreamVLN 模块根目录",
        "修复动作：显式补齐 PYTHONPATH 后重新启动",
        f"检查点分片加载：{shards.group(1)}/{shards.group(2)}",
        f"重载状态：{status}",
        f"适配器类型：{peft_type}｜LoRA r={lora_r}｜推理态 trainable={trainable}",
    ]


def _wrap(text: str, limit: int = 46) -> list[str]:
    return [text[index : index + limit] for index in range(0, len(text), limit)] or [""]


def _render_frame(title: str, events: list[str], visible: int, source_hash: str, output: Path) -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), (6, 13, 23))
    draw = ImageDraw.Draw(image)
    title_font = _font(58)
    body_font = _font(34)
    small_font = _font(26)
    mono_font = _font(31)
    draw.rounded_rectangle((70, 60, WIDTH - 70, HEIGHT - 60), radius=32, fill=(12, 25, 40), outline=(51, 75, 98), width=2)
    draw.text((120, 100), title, font=title_font, fill=(245, 174, 80))
    draw.text((122, 180), "真实日志回放（路径、账号、地址已脱敏）", font=small_font, fill=(179, 198, 220))
    draw.rounded_rectangle((110, 235, WIDTH - 110, 880), radius=18, fill=(3, 10, 18), outline=(43, 69, 91), width=2)
    y = 285
    for index, event in enumerate(events):
        if index >= visible:
            break
        colour = (88, 222, 168) if index == visible - 1 else (221, 232, 244)
        prefix = "✓" if index < visible - 1 else "›"
        for line_index, line in enumerate(_wrap(event)):
            lead = prefix if line_index == 0 else " "
            draw.text((155, y), f"{lead} {line}", font=mono_font, fill=colour)
            y += 62
        y += 22
    cursor = "▋" if visible < len(events) else "完成"
    draw.text((155, 810), cursor, font=body_font, fill=(77, 204, 238))
    draw.text((120, 940), f"证据哈希 SHA-256：{source_hash[:16]}…", font=small_font, fill=(135, 158, 184))
    draw.text((WIDTH - 420, 940), "公开版只展示可复核结果", font=small_font, fill=(135, 158, 184))
    image.save(output)


def render_replay(title: str, events: list[str], source_bytes: bytes, output: Path, duration_s: float = 12.0) -> None:
    if not events:
        raise ValueError("events must not be empty")
    output.parent.mkdir(parents=True, exist_ok=True)
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    with tempfile.TemporaryDirectory(prefix="aima-log-replay-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        frame_duration = duration_s / len(events)
        frames: list[Path] = []
        for index in range(1, len(events) + 1):
            frame = temp_dir / f"frame-{index:02d}.png"
            _render_frame(title, events, index, source_hash, frame)
            frames.append(frame)
        concat = temp_dir / "frames.txt"
        lines: list[str] = []
        for frame in frames:
            lines.extend([f"file '{frame.as_posix()}'", f"duration {frame_duration:.6f}"])
        lines.append(f"file '{frames[-1].as_posix()}'")
        concat.write_text("\n".join(lines) + "\n", encoding="utf-8")
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat),
                "-t",
                f"{duration_s:.3f}",
                "-vf",
                f"fps={FPS},format=yuv420p",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-movflags",
                "+faststart",
                str(output),
            ],
            check=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["single-batch", "adapter-reload"], required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--failure", type=Path)
    parser.add_argument("--success", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=12.0)
    args = parser.parse_args()

    if args.mode == "single-batch":
        if args.input is None:
            parser.error("--input is required for single-batch")
        payload = args.input.read_bytes()
        events = extract_single_batch_events(payload.decode("utf-8", errors="ignore"))
        title = "Stage 2｜单批前后向真实日志"
    else:
        if args.failure is None or args.success is None:
            parser.error("--failure and --success are required for adapter-reload")
        failure = args.failure.read_bytes()
        success = args.success.read_bytes()
        payload = failure + b"\n" + success
        events = extract_reload_events(
            failure.decode("utf-8", errors="ignore"),
            success.decode("utf-8", errors="ignore"),
        )
        title = "Stage 2｜LoRA 新进程重载真实日志"
    render_replay(title, events, payload, args.output, args.duration)


if __name__ == "__main__":
    main()
