"""Build evidence GIFs and a 55-second silent, caption-burned Douyin video."""

from __future__ import annotations

import argparse
import glob
import json
import shutil
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
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
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
    d.text((70, 1670), "非官方实验记录", fill=MUTED, font=font(32))
    return canvas


def make_outro(base_success: int, lora_success: int) -> Image.Image:
    canvas = Image.new("RGB", (1080, 1920), BG)
    d = ImageDraw.Draw(canvas)
    d.text((70, 300), "最后，把结果说清楚", fill=ORANGE, font=font(48))
    d.text((70, 420), f"基础模型：{base_success}/10", fill=WHITE, font=font(66))
    d.text((70, 530), f"低秩适配：{lora_success}/10", fill=WHITE, font=font(66))
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


def screenshot_to_vertical(image_path: Path, title: str, detail: str) -> Image.Image:
    """Show an original capture frame directly, with a Chinese evidence label."""
    canvas = Image.new("RGB", (1080, 1920), BG)
    d = ImageDraw.Draw(canvas)
    d.text((70, 105), title, fill=ORANGE, font=font(46))
    d.rounded_rectangle((55, 235, 1025, 1410), radius=26, fill=PANEL)
    with Image.open(image_path).convert("RGB") as source:
        image = ImageOps.contain(source, (920, 1050), method=Image.Resampling.LANCZOS)
    x = (1080 - image.width) // 2
    y = 300 + (1050 - image.height) // 2
    canvas.paste(image, (x, y))
    d.text((70, 1500), "真实采集截图", fill=WHITE, font=font(40))
    d.text((70, 1590), detail, fill=MUTED, font=font(30))
    d.text((70, 1730), "不是人工智能生成图，来自仿真运行现场", fill=MUTED, font=font(28))
    return canvas


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--cards-dir", type=Path, required=True)
    parser.add_argument("--metrics", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    out_dir = args.out_dir.expanduser().resolve()
    cards_dir = args.cards_dir.expanduser().resolve()
    metrics = json.loads(args.metrics.expanduser().resolve().read_text(encoding="utf-8"))
    base_success = int(metrics["base_model"]["model_evaluation"]["summary"]["success_0_5"])
    lora_success = int(metrics["lora_model"]["model_evaluation"]["summary"]["success_0_5"])
    out_dir.mkdir(parents=True, exist_ok=True)

    names = ["train-1001-start.jpg", "train-1025-mid.jpg", "stage0-before-block.jpg", "stage3-base-2004-mid.jpg", "stage3-base-2004-end.jpg"]
    gif_frames = load_frames(source, names, (960, 540))
    gif_path = out_dir / "stage1-smoke-controller.gif"
    gif_frames[0].save(gif_path, save_all=True, append_images=gif_frames[1:], duration=600, loop=0, disposal=2)

    card_paths = [cards_dir / f"carousel-{i:02d}.jpg" for i in range(1, 21)]
    missing = [str(p) for p in card_paths if not p.is_file()]
    if missing:
        raise FileNotFoundError("缺少轮播卡片: " + ", ".join(missing))
    real_screenshots = [
        (source / "train-1001-start.jpg", "真实观测一：训练起点", "第一视角彩色图、深度图与位姿同步保存"),
        (source / "train-1025-mid.jpg", "真实观测二：货架细节", "50 条轨迹覆盖不同起点和朝向"),
        (source / "stage0-before-block.jpg", "真实观测三：近障碍", "头部深度安全门会拒绝危险前进"),
        (source / "stage3-base-2004-mid.jpg", "真实观测四：模型闭环", "动作来自视觉语言模型生成，不是控制器代跑"),
        (source / "stage3-base-2004-end.jpg", "真实观测五：失败终点", "失败轨迹同样进入十条总体指标"),
    ]
    missing_real = [str(path) for path, _, _ in real_screenshots if not path.is_file()]
    if missing_real:
        raise FileNotFoundError("缺少真实采集截图: " + ", ".join(missing_real))
    vertical: list[Image.Image] = [make_intro()]
    durations: list[float] = [3.0]
    real_index = 0
    for index, card_path in enumerate(card_paths, start=1):
        vertical.append(card_to_vertical(card_path))
        durations.append(1.75)
        if index % 4 == 0:
            path, title, detail = real_screenshots[real_index]
            vertical.append(screenshot_to_vertical(path, title, detail))
            durations.append(2.5)
            real_index += 1
    vertical.append(make_outro(base_success, lora_success))
    durations.append(4.5)
    assert len(vertical) == len(durations) == 27
    assert abs(sum(durations) - 55.0) < 1e-6

    try:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("ffmpeg is not installed")
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f"需要 ffmpeg 才能输出视频: {exc}") from exc

    mp4_path = out_dir / "douyin-vln-retrospective-55s.mp4"
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
                "55",
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
