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
        ("一句话，让机器人在 3D 场景里找目标", "先把闭环接口做实，再谈模型效果。"),
        ("先说清楚：这是非官方适配", "流程参考 AIMA 指南，没有使用课程私有包。"),
        ("Stage 0：看见、转向、记录", "G2 刚体代理 + 头部相机 + RGB/depth/pose。"),
        ("Stage 1：3 + 50 + 10", "3 条冒烟、50 条训练、10 条固定种子评测。"),
        ("每一步都留下证据", "等待两个渲染帧，保存图像、depth、位姿和碰撞。"),
        ("控制器闭环结果", "fallback 栅格下，10/10 在 0.5m 内 STOP。"),
        ("为什么不包装成成功案例？", "USD AABB 遍历会触发引擎退出；模型 LoRA 仍未完成。"),
        ("下一轮：兼容资产 + base/LoRA 对照", "真实结果完成后，再决定是否发布升级版。"),
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
