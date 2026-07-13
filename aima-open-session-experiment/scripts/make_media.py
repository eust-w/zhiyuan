"""Build the smoke GIF and the expanded Chinese 90-second Douyin video."""

from __future__ import annotations

import argparse
import glob
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


BG = (10, 15, 24)
WHITE = (246, 248, 255)
MUTED = (185, 199, 218)
ORANGE = (245, 174, 80)
PANEL = (21, 30, 44)


def font(size: int):
    paths = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    paths += glob.glob("/System/Library/AssetsV2/*/*/AssetData/Hei.ttf")
    paths += glob.glob("/System/Library/AssetsV2/*/*/AssetData/Lantinghei.ttc")
    for path in paths:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default()


def load_frames(source: Path, names: list[str], size: tuple[int, int]) -> list[Image.Image]:
    frames: list[Image.Image] = []
    for name in names:
        with Image.open(source / name).convert("RGB") as image:
            frames.append(ImageOps.fit(image, size, method=Image.Resampling.LANCZOS))
    if len(frames) < 2:
        raise ValueError("至少需要两张真实采集帧")
    return frames


def make_intro() -> Image.Image:
    canvas = Image.new("RGB", (1080, 1920), BG)
    d = ImageDraw.Draw(canvas)
    d.text((70, 270), "我给机器人一句话", fill=ORANGE, font=font(48))
    d.text((70, 390), "走向红色目标，然后停下", fill=WHITE, font=font(68))
    d.rounded_rectangle((70, 610, 1010, 980), radius=28, fill=PANEL)
    d.text((120, 690), "20 张图看懂一次", fill=WHITE, font=font(48))
    d.text((120, 785), "非官方视觉语言导航实验", fill=ORANGE, font=font(48))
    d.text((70, 1580), "真实截图 · 真实模型动作 · 真实失败指标", fill=MUTED, font=font(32))
    d.text((70, 1670), "智元布道师个人实验", fill=MUTED, font=font(32))
    return canvas


def make_outro() -> Image.Image:
    canvas = Image.new("RGB", (1080, 1920), BG)
    d = ImageDraw.Draw(canvas)
    d.text((70, 300), "最后，把结果说清楚", fill=ORANGE, font=font(48))
    d.text((70, 420), "基础模型：0/10", fill=WHITE, font=font(66))
    d.text((70, 530), "低秩适配：0/10", fill=WHITE, font=font(66))
    d.rounded_rectangle((70, 720, 1010, 1120), radius=28, fill=PANEL)
    d.text((120, 800), "成功率为零", fill=WHITE, font=font(50))
    d.text((120, 900), "但模型 → 接口 → 仿真 → 指标", fill=ORANGE, font=font(40))
    d.text((120, 980), "这一条闭环可以复核", fill=ORANGE, font=font(40))
    d.text((70, 1510), "下一轮：兼容资产 · 有效深度 · 目标数据", fill=MUTED, font=font(30))
    d.text((70, 1640), "非官方 · 非商业研究演示 · 不提交榜单", fill=MUTED, font=font(30))
    return canvas


def card_to_vertical(card_path: Path) -> Image.Image:
    with Image.open(card_path).convert("RGB") as card:
        card = ImageOps.contain(card, (1080, 1440), method=Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (1080, 1920), BG)
    canvas.paste(card, ((1080 - card.width) // 2, 240))
    return canvas


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--cards-dir", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    out_dir = args.out_dir.expanduser().resolve()
    cards_dir = args.cards_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    names = ["P1-smoke-0000.jpg", "P1-smoke-0008.jpg", "P1-smoke-0016.jpg", "P1-smoke-0024.jpg", "P1-smoke-0026.jpg"]
    gif_frames = load_frames(source, names, (960, 540))
    gif_path = out_dir / "stage1-smoke-controller.gif"
    gif_frames[0].save(gif_path, save_all=True, append_images=gif_frames[1:], duration=600, loop=0, disposal=2)

    card_paths = [cards_dir / f"carousel-{i:02d}.jpg" for i in range(1, 21)]
    missing = [str(p) for p in card_paths if not p.is_file()]
    if missing:
        raise FileNotFoundError("缺少轮播卡片: " + ", ".join(missing))
    vertical = [make_intro()] + [card_to_vertical(path) for path in card_paths] + [make_outro()]
    durations = [5.0] + [4.0] * 20 + [5.0]
    assert sum(durations) == 90.0

    try:
        import imageio_ffmpeg

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f"需要 ffmpeg 才能输出视频: {exc}") from exc

    mp4_path = out_dir / "stage1-smoke-retrospective-vertical-90s.mp4"
    with tempfile.TemporaryDirectory(prefix="aima-media-") as temp:
        temp_dir = Path(temp)
        paths: list[Path] = []
        for i, frame in enumerate(vertical):
            path = temp_dir / f"frame-{i:03d}.png"
            frame.save(path)
            paths.append(path)
        concat = temp_dir / "frames.txt"
        lines: list[str] = []
        for path, duration in zip(paths, durations):
            lines += [f"file '{path}'", f"duration {duration:.3f}"]
        lines.append(f"file '{paths[-1]}'")
        concat.write_text("\n".join(lines) + "\n", encoding="utf-8")
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat),
                "-t",
                "90",
                "-vf",
                "fps=30,format=yuv420p",
                "-an",
                "-c:v",
                "libx264",
                "-movflags",
                "+faststart",
                str(mp4_path),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    print(gif_path)
    print(mp4_path)


if __name__ == "__main__":
    main()
