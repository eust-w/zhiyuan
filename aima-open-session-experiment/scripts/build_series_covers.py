"""Build four Chinese B站 cover drafts from checked-in evidence images."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
FONT_CANDIDATES = (
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
)


def font(size: int) -> ImageFont.FreeTypeFont:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def fit_background(path: Path, size: tuple[int, int]) -> Image.Image:
    image = Image.open(path).convert("RGB")
    scale = max(size[0] / image.width, size[1] / image.height)
    image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    left = (image.width - size[0]) // 2
    top = (image.height - size[1]) // 2
    return image.crop((left, top, left + size[0], top + size[1])).filter(ImageFilter.GaussianBlur(0.6))


def build(out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    items = [
        ("stage0", "机器人会动，不等于导航闭环", "动作映射 · 两帧等待 · 安全拒绝", ROOT / "assets/screenshots/v3/stage0-after-block.jpg", "真实结果图"),
        ("stage1", "50 条训练与 10 条评测怎么采", "RGB-D · pose · annotations · sidecar", ROOT / "assets/screenshots/v3/stage1-validation.png", "真实结果图"),
        ("stage2", "loss 下降，不代表会导航", "LoRA 四道验证门 · 59 步更新", ROOT / "assets/screenshots/v3/stage2-loss-curve.png", "真实结果图"),
        ("stage3", "闭环是真的，success 仍是 0/10", "base / LoRA · held-out 配对评测", ROOT / "assets/screenshots/v3/stage3-paired-metrics.png", "真实指标图"),
    ]
    outputs: list[Path] = []
    for stage, title, subtitle, source, label in items:
        canvas = fit_background(source, (1920, 1080)).convert("RGBA")
        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        draw.rectangle((0, 0, 1920, 1080), fill=(5, 12, 25, 110))
        draw.rectangle((72, 72, 700, 160), fill=(8, 30, 52, 230), outline=(77, 204, 238, 255), width=3)
        draw.text((104, 98), "GenieSim × StreamVLN  ·  四期教程", fill=(230, 246, 255, 255), font=font(34))
        draw.rounded_rectangle((90, 300, 1770, 760), radius=32, fill=(5, 12, 25, 210), outline=(245, 174, 80, 255), width=4)
        draw.text((145, 365), stage.upper(), fill=(245, 174, 80, 255), font=font(58))
        draw.text((145, 455), title, fill=(248, 251, 255, 255), font=font(76))
        draw.text((150, 585), subtitle, fill=(180, 220, 235, 255), font=font(42))
        draw.rounded_rectangle((1430, 86, 1810, 160), radius=18, fill=(8, 30, 52, 230))
        draw.text((1490, 105), label, fill=(245, 174, 80, 255), font=font(30))
        draw.text((145, 880), "非官方等价适配  ·  主指标 success@0.5m  ·  失败也公开", fill=(225, 235, 245, 255), font=font(32))
        result = Image.alpha_composite(canvas, overlay).convert("RGB")
        path = out / f"{stage}-cover.png"
        result.save(path, format="PNG", optimize=True)
        outputs.append(path)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "assets/series/covers")
    args = parser.parse_args()
    print("\n".join(str(path) for path in build(args.output.resolve())))


if __name__ == "__main__":
    main()
