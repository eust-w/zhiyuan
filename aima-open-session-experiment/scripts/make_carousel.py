"""Create eight factual Douyin carousel cards from captured RGB frames."""

from __future__ import annotations

import argparse
import glob
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def font(size: int):
    paths = glob.glob("/System/Library/AssetsV2/*/*/AssetData/Hei.ttf") + glob.glob("/System/Library/AssetsV2/*/*/AssetData/Lantinghei.ttc")
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    out = args.out_dir.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    names = ["P1-smoke-0000.jpg", "P1-smoke-0008.jpg", "P1-smoke-0016.jpg", "P1-smoke-0024.jpg", "P1-smoke-0026.jpg"]
    frames = [ImageOps.fit(Image.open(source / name).convert("RGB"), (980, 700), method=Image.Resampling.LANCZOS) for name in names]
    cards = [
        ("一句话，让机器人找红色目标", "Walk toward the red beacon and stop. 这次把模型输出真的送回 GenieSim。"),
        ("先说清楚：这是非官方适配", "流程参考 AIMA 指南，没有课程私有适配包，不提交 Open Session 榜单。"),
        ("感知 → 模型 → 动作 → 结果", "G2 头部相机保存 RGB/depth/pose，StreamVLN 生成 STOP/前进/左转/右转。"),
        ("同一批 10 条 held-out", "eval-2001…2010 固定种子；base 与 LoRA 读取同一组指令和初始状态。"),
        ("不是只看一张成功截图", "每步记录模型输出、HTTP step、位姿、目标距离、blocked、碰撞和终止状态。"),
        ("base：0/10 达到 0.5m", "平均最终距离 3.87m；SPL@0.5=0；碰撞 5 次；SPL@3m=0.093。"),
        ("LoRA：0/10 达到 0.5m", "平均最终距离 4.30m；SPL@0.5=0；碰撞 0 次；SPL@3m=0.083。"),
        ("失败也要给出下一步", "当前是完整模型闭环失败复盘：继续换兼容 USD 资产、改善深度与训练数据，再复测。"),
    ]
    title_font = font(54)
    body_font = font(32)
    # Hei.ttf has bitmap gaps at 24px; 28px renders all Chinese glyphs.
    small_font = font(28)
    for index, (title, body) in enumerate(cards, 1):
        canvas = Image.new("RGB", (1080, 1440), (10, 15, 24))
        frame = frames[(index - 1) % len(frames)]
        canvas.paste(frame, ((1080 - frame.width) // 2, 180))
        draw = ImageDraw.Draw(canvas)
        draw.text((50, 45), f"{index:02d}/08  智元布道师个人实验", fill=(245, 174, 80), font=small_font)
        draw.text((50, 980), title, fill=(246, 248, 255), font=title_font)
        draw.rounded_rectangle((42, 1070, 1038, 1295), radius=20, fill=(21, 30, 44))
        draw.text((75, 1145), body, fill=(235, 241, 250), font=body_font)
        draw.text((50, 1360), "非官方 · 非商业研究演示 · 不提交 Open Session 榜单", fill=(180, 196, 216), font=small_font)
        canvas.save(out / f"carousel-{index:02d}.jpg", quality=92, optimize=True)


if __name__ == "__main__":
    main()
