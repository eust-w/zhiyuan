"""Render Chinese 3:4 step cards for the four Xiaohongshu packages."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
SIZE = (1080, 1440)
NAVY = (7, 15, 27, 255)
PANEL = (10, 27, 45, 238)
WHITE = (244, 248, 255, 255)
MUTED = (184, 204, 225, 255)
ORANGE = (245, 174, 80, 255)
CYAN = (77, 204, 238, 255)


CARD_COPY = {
    "stage0": [
        "先确认 G2、头部彩色相机与深度相机持续输出；这一步只证明环境可观测。",
        "停止=0、前进0.25米=1、左转15度=2、右转15度=3；后退只用于调试。",
        "动作由仿真主线程执行，至少等待两个渲染帧，再保存图像、深度和位姿。",
        "用位姿矩阵计算平面位移，验证前进增量接近0.25米，而不是只凭肉眼。",
        "前方深度过近时标记 blocked，危险前进必须被拒绝。",
        "拒绝前后 pose 必须一致；只有提示而没有位姿对照不算通过。",
        "请求入队、主线程动作、相对路径回传；文件必须留在实验根目录。",
        "Stage 0 只证明控制和观测可信，不代表模型已经会导航。",
    ],
    "stage1": [
        "先采三条冒烟轨迹，发现深度为空、动作错位或目标不可达时立即停止批量。",
        "训练使用1001–1050，评测使用2001–2010；同一种子必须得到可追溯的采样结果。",
        "五十条训练和十条留出从种子层面隔离，评测样本不得进入 LoRA 更新。",
        "每一步同步保存彩色图、深度、四乘四位姿、动作、距离和碰撞状态。",
        "公开 annotations 首动作写负一，图像数与动作数一致，不追加最终停止。",
        "完整停止、深度、轨迹、目标牌和碰撞信息进入独立 sidecar。",
        "障碍物投影为五厘米栅格，再按机器人 footprint 膨胀五厘米。",
        "验收数量、格式、帧数、动作数、路径安全和图片可解码，失败样本不能静默跳过。",
        "至少抽查五条轨迹，核对目标可见性、深度、轨迹线和敏感信息。",
    ],
    "stage2": [
        "Isaac 使用预装 Python 3.11，StreamVLN 使用独立 Python 3.9，避免依赖互相污染。",
        "LoRA 固定 r=8、alpha=16、dropout=0.05、批量1和学习率2×10⁻⁵。",
        "第一道门只读取数据，先排除路径、格式、帧数和首动作错误。",
        "第二道门运行一个 batch，确认 loss、梯度与输出都没有 NaN 或 Inf。",
        "完整训练记录59个真实更新步，不能用空循环或零 loss 代替。",
        "loss 从0.4167降到0.0823，只能证明优化发生，不等于导航成功。",
        "峰值显存约27.19GiB；没有 OOM 证据时不切换四比特路径。",
        "关闭训练进程后重新加载 adapter，验证文件、配置、形状和哈希。",
        "重载通过仍不能证明模型会规划；真正答案必须来自 held-out 闭环。",
    ],
    "stage3": [
        "模型读取观测、生成动作、驱动 GenieSim 并接收下一帧，形成真实闭环。",
        "base 与 LoRA 使用完全相同的十条 held-out，逐条重置缓存、队列和历史。",
        "主成功半径固定为0.5米：base 0/10，LoRA 0/10。",
        "三米只作辅助观察：base 2/10，LoRA 1/10，不能替代主指标。",
        "平均最终距离：base 3.989米，LoRA 4.686米；少走不等于更接近。",
        "base 平均路径9.675米、133.9步；LoRA 5.5米、53.2步。",
        "碰撞尝试分别为132与45；碰撞变少可能只是更早停止。",
        "停止、前进、左转、右转必须和请求数、blocked 数及位姿变化一起解释。",
        "几何、目标可见性和现实 checkpoint 到仿真相机域都可能造成失败。",
        "下一轮先做安全门、目标牌和相机域消融，再按同一0.5米协议重评。",
    ],
}


def font(size: int):
    for candidate in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
    ):
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def lines(text: str, limit: int) -> list[str]:
    result: list[str] = []
    current = ""
    for char in text:
        if len(current) >= limit:
            result.append(current)
            current = ""
        current += char
    if current:
        result.append(current)
    return result


def label_for(source: str) -> tuple[str, tuple[int, int, int, int]]:
    if "ai-diagrams" in source:
        return "AI 示意图", CYAN
    if "/media/" in source or source.lower().endswith(".gif"):
        return "真实录屏帧", ORANGE
    if "/plots/" in source:
        return "真实指标图", ORANGE
    return "真实结果图", ORANGE


def source_image(path: Path, size: tuple[int, int]) -> Image.Image:
    with Image.open(path) as opened:
        opened.seek(0)
        image = opened.convert("RGB")
    background = ImageOps.fit(image, size, method=Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(22))
    background = Image.blend(background, Image.new("RGB", size, (8, 16, 28)), 0.28)
    foreground = image.copy()
    foreground.thumbnail((size[0] - 36, size[1] - 36), Image.Resampling.LANCZOS)
    x = (size[0] - foreground.width) // 2
    y = (size[1] - foreground.height) // 2
    background.paste(foreground, (x, y))
    return background


def render_card(stage: str, series_title: str, card_title: str, copy: str, source: str, index: int, total: int, output: Path) -> dict[str, object]:
    canvas = Image.new("RGBA", SIZE, NAVY)
    draw = ImageDraw.Draw(canvas)
    label, accent = label_for(source)
    draw.rounded_rectangle((54, 50, 1026, 132), radius=20, fill=PANEL, outline=accent, width=3)
    draw.text((82, 73), f"{stage.upper()}  ·  {index:02}/{total:02}", fill=accent, font=font(30))
    label_box = draw.textbbox((0, 0), label, font=font(28))
    draw.text((990 - (label_box[2] - label_box[0]), 76), label, fill=accent, font=font(28))

    title_y = 175
    for line in lines(card_title, 14)[:2]:
        draw.text((70, title_y), line, fill=WHITE, font=font(60))
        title_y += 78
    draw.text((72, title_y + 4), series_title, fill=MUTED, font=font(27))

    frame = (60, 360, 1020, 1035)
    media = source_image(ROOT / source, (frame[2] - frame[0], frame[3] - frame[1]))
    canvas.alpha_composite(media.convert("RGBA"), (frame[0], frame[1]))
    draw.rounded_rectangle(frame, radius=24, outline=accent, width=4)

    draw.rounded_rectangle((60, 1065, 1020, 1335), radius=26, fill=PANEL)
    body_y = 1102
    for line in lines(copy, 23)[:4]:
        draw.text((94, body_y), line, fill=WHITE, font=font(35))
        body_y += 52
    draw.text((94, 1300), "非官方等价适配｜主指标 success@0.5m", fill=MUTED, font=font(25))

    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output, format="PNG", optimize=True)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    try:
        manifest_output = str(output.relative_to(ROOT))
    except ValueError:
        manifest_output = str(output)
    return {
        "index": index,
        "title": card_title,
        "copy": copy,
        "source": source,
        "label": label,
        "output": manifest_output,
        "width": SIZE[0],
        "height": SIZE[1],
        "sha256": digest,
    }


def build(inventory: Path, output_root: Path) -> list[Path]:
    data = json.loads(inventory.read_text(encoding="utf-8"))
    manifests: list[Path] = []
    for episode in data["episodes"]:
        stage = episode["episode"]
        cards = episode["cards"]
        evidence = episode["evidence_images"]
        copies = CARD_COPY[stage]
        if not (len(cards) == len(copies) and len(evidence) >= len(cards)):
            raise ValueError(f"card inventory mismatch for {stage}")
        directory = output_root / stage
        rendered = [
            render_card(stage, episode["title"], title, copies[index], evidence[index], index + 1, len(cards), directory / f"card-{index + 1:02}.png")
            for index, title in enumerate(cards)
        ]
        manifest = directory / "manifest.json"
        manifest.write_text(json.dumps({
            "schema_version": "aima-vln-xhs-cards/v1",
            "episode": stage,
            "status": "draft",
            "count": len(rendered),
            "cards": rendered,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifests.append(manifest)
    return manifests


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=ROOT / "content/series/platform-content.json")
    parser.add_argument("--output", type=Path, default=ROOT / "assets/series/xiaohongshu")
    args = parser.parse_args()
    print("\n".join(str(path) for path in build(args.inventory.resolve(), args.output.resolve())))


if __name__ == "__main__":
    main()
