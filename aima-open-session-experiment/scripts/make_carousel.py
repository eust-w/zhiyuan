"""Create a twenty-card, Chinese-only Douyin carousel.

The visual language intentionally matches the original cards: near-black navy
background, one rounded evidence panel, large white Chinese title, and a compact
evidence paragraph. Numeric overlays are loaded from ``eval_result.json`` so the
carousel cannot silently drift away from the authoritative metrics.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
BG = (10, 15, 24)
PANEL = (21, 30, 44)
WHITE = (246, 248, 255)
MUTED = (185, 199, 218)
ORANGE = (245, 174, 80)
CYAN = (77, 204, 238)
PINK = (241, 104, 177)


def font(size: int):
    paths = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
    ]
    paths += glob.glob("/System/Library/AssetsV2/*/*/AssetData/Hei.ttf")
    paths += glob.glob("/System/Library/AssetsV2/*/*/AssetData/Lantinghei.ttc")
    paths += ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for char in paragraph:
            candidate = current + char
            if draw.textbbox((0, 0), candidate, font=fnt)[2] <= width or not current:
                current = candidate
            else:
                lines.append(current)
                current = char
        lines.append(current)
    return lines


def draw_wrapped(draw, xy, text, fnt, fill, width, spacing=10):
    x, y = xy
    line_h = draw.textbbox((0, 0), "中Ag", font=fnt)[3] + spacing
    for line in wrap(draw, text, fnt, width):
        draw.text((x, y), line, font=fnt, fill=fill)
        y += line_h
    return y


def load_metric(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def summary(metrics: dict, variant: str) -> dict:
    return metrics[variant]["model_evaluation"]["summary"]


def action_totals(s: dict) -> dict[str, int]:
    totals = {"停止": 0, "前进": 0, "左转": 0, "右转": 0}
    for episode in s["episodes_detail"]:
        counts = episode.get("action_counts", {})
        totals["停止"] += int(counts.get("stop", 0))
        totals["前进"] += int(counts.get("forward", 0))
        totals["左转"] += int(counts.get("left", 0))
        totals["右转"] += int(counts.get("right", 0))
    return totals


def chart_base_lora(metrics: dict, out: Path) -> None:
    canvas = Image.new("RGB", (980, 700), PANEL)
    d = ImageDraw.Draw(canvas)
    title = font(38)
    label = font(26)
    d.text((36, 26), "基础模型与低秩适配对比", fill=WHITE, font=title)
    names = [("半米成功率", "success_0_5", 10), ("三米成功率", "success_3", 10), ("三米路径效率", "mean_spl_3", 1)]
    base = summary(metrics, "base_model")
    lora = summary(metrics, "lora_model")
    left, top, width, height = 90, 125, 820, 420
    d.line((left, top + height, left + width, top + height), fill=MUTED, width=2)
    for tick in range(6):
        y = top + height - tick * height / 5
        d.line((left, y, left + width, y), fill=(45, 59, 77), width=1)
        d.text((30, y - 14), f"{tick * 20}%", fill=MUTED, font=label)
    group_w = width / len(names)
    for i, (name, key, scale) in enumerate(names):
        x0 = left + i * group_w + 55
        vals = [base[key] / scale * 100 / 100, lora[key] / scale * 100 / 100]
        # The first two metrics are ratios, SPL is already a ratio.
        vals = [float(base[key]) / (10 if scale == 10 else 1), float(lora[key]) / (10 if scale == 10 else 1)]
        for j, (v, color) in enumerate(zip(vals, [CYAN, PINK])):
            h = min(height, max(3, v * height))
            x = x0 + j * 72
            d.rounded_rectangle((x, top + height - h, x + 48, top + height), radius=8, fill=color)
            d.text((x + 7, top + height - h - 30), f"{v * 100:.1f}%", fill=WHITE, font=label)
        d.text((x0 - 22, top + height + 20), name, fill=WHITE, font=label)
    d.rounded_rectangle((650, 585, 730, 620), radius=8, fill=CYAN)
    d.text((742, 587), "基础模型", fill=WHITE, font=label)
    d.rounded_rectangle((650, 635, 730, 670), radius=8, fill=PINK)
    d.text((742, 637), "低秩适配", fill=WHITE, font=label)
    canvas.save(out, quality=94)


def chart_episode_distance(metrics: dict, out: Path) -> None:
    canvas = Image.new("RGB", (980, 700), PANEL)
    d = ImageDraw.Draw(canvas)
    title, label = font(38), font(24)
    d.text((36, 26), "十条留出评测的最终距离", fill=WHITE, font=title)
    base = summary(metrics, "base_model")["episodes_detail"]
    lora = summary(metrics, "lora_model")["episodes_detail"]
    left, top, width, height = 85, 125, 835, 440
    max_y = max(6.0, max(e["final_distance_to_goal"] for e in base + lora) + 0.4)
    for tick in range(7):
        yv = tick * max_y / 6
        y = top + height - tick * height / 6
        d.line((left, y, left + width, y), fill=(45, 59, 77), width=1)
        d.text((24, y - 12), f"{yv:.1f}米", fill=MUTED, font=label)
    def points(entries):
        result = []
        for i, e in enumerate(entries):
            x = left + i * width / 9
            y = top + height - e["final_distance_to_goal"] / max_y * height
            result.append((x, y))
        return result
    for entries, color in [(base, CYAN), (lora, PINK)]:
        pts = points(entries)
        d.line(pts, fill=color, width=6)
        for x, y in pts:
            d.ellipse((x - 7, y - 7, x + 7, y + 7), fill=color, outline=WHITE, width=2)
    for i in range(10):
        x = left + i * width / 9
        d.text((x - 18, top + height + 18), str(2001 + i), fill=MUTED, font=label)
    d.line((650, 625, 700, 625), fill=CYAN, width=6)
    d.text((712, 612), "基础模型", fill=WHITE, font=label)
    d.line((650, 665, 700, 665), fill=PINK, width=6)
    d.text((712, 652), "低秩适配", fill=WHITE, font=label)
    canvas.save(out, quality=94)


def chart_actions(metrics: dict, out: Path) -> None:
    canvas = Image.new("RGB", (980, 700), PANEL)
    d = ImageDraw.Draw(canvas)
    title, label = font(38), font(26)
    d.text((36, 26), "模型动作计数", fill=WHITE, font=title)
    totals = [action_totals(summary(metrics, "base_model")), action_totals(summary(metrics, "lora_model"))]
    names = ["停止", "前进", "左转", "右转"]
    colors = [ORANGE, CYAN, (115, 164, 255), PINK]
    left, top, width, height = 95, 135, 820, 390
    maxv = max(sum(t.values()) for t in totals)
    group_w = width / 4
    for i, name in enumerate(names):
        x0 = left + i * group_w + 35
        for j, (t, color) in enumerate(zip(totals, [CYAN, PINK])):
            v = t[name]
            h = max(4, v / maxv * height)
            x = x0 + j * 60
            d.rounded_rectangle((x, top + height - h, x + 42, top + height), radius=8, fill=color)
            d.text((x + 2, top + height - h - 28), str(v), fill=WHITE, font=label)
        d.text((x0 - 3, top + height + 20), name, fill=WHITE, font=label)
    d.text((95, 610), "动作由模型生成，再交给仿真执行；不是控制器代跑", fill=MUTED, font=label)
    d.rounded_rectangle((650, 585, 700, 615), radius=8, fill=CYAN)
    d.text((712, 581), "基础模型", fill=WHITE, font=label)
    d.rounded_rectangle((650, 630, 700, 660), radius=8, fill=PINK)
    d.text((712, 626), "低秩适配", fill=WHITE, font=label)
    canvas.save(out, quality=94)


def chart_schema(out: Path) -> None:
    canvas = Image.new("RGB", (980, 700), PANEL)
    d = ImageDraw.Draw(canvas)
    title, label = font(38), font(26)
    d.text((36, 26), "公开数据与完整旁路记录", fill=WHITE, font=title)
    boxes = [(70, 150, "彩色帧", CYAN), (275, 150, "动作数组", ORANGE), (480, 150, "深度与位姿", (115, 164, 255)), (685, 150, "碰撞与距离", PINK)]
    for x, y, text, color in boxes:
        d.rounded_rectangle((x, y, x + 170, y + 120), radius=18, outline=color, width=5, fill=(16, 25, 39))
        d.text((x + 34, y + 45), text, fill=WHITE, font=label)
    d.line((145, 270, 820, 270), fill=MUTED, width=3)
    d.polygon([(810, 260), (840, 270), (810, 280)], fill=MUTED)
    d.rounded_rectangle((90, 365, 420, 550), radius=22, fill=(14, 23, 36), outline=CYAN, width=4)
    d.text((135, 405), "公开标注", fill=WHITE, font=font(34))
    d.text((135, 470), "首动作 -1 · 不放最终停止", fill=MUTED, font=label)
    d.rounded_rectangle((555, 365, 890, 550), radius=22, fill=(14, 23, 36), outline=ORANGE, width=4)
    d.text((600, 405), "完整旁路记录", fill=WHITE, font=font(34))
    d.text((600, 470), "深度 · 轨迹 · 碰撞 · 目标", fill=MUTED, font=label)
    canvas.save(out, quality=94)


def chart_lora(out: Path) -> None:
    canvas = Image.new("RGB", (980, 700), PANEL)
    d = ImageDraw.Draw(canvas)
    d.text((36, 26), "低秩适配训练配置", fill=WHITE, font=font(38))
    items = [
        ("秩", "8"), ("缩放", "16"), ("丢弃率", "0.05"), ("轮数", "1"),
        ("批量", "1"), ("学习率", "0.00002"), ("精度", "脑浮点"), ("梯度检查点", "开启"),
    ]
    for i, (k, v) in enumerate(items):
        row, col = divmod(i, 2)
        x, y = 70 + col * 430, 130 + row * 125
        d.rounded_rectangle((x, y, x + 360, y + 92), radius=16, fill=(16, 25, 39), outline=CYAN if col == 0 else ORANGE, width=3)
        d.text((x + 24, y + 18), k, fill=MUTED, font=font(24))
        d.text((x + 24, y + 50), v, fill=WHITE, font=font(30))
    d.text((70, 640), "训练通过与导航效果分开统计，不能用保存权重代替成功率", fill=MUTED, font=font(24))
    canvas.save(out, quality=94)


def chart_gates(out: Path) -> None:
    canvas = Image.new("RGB", (980, 700), PANEL)
    d = ImageDraw.Draw(canvas)
    d.text((36, 26), "训练前后的四道验证门", fill=WHITE, font=font(38))
    gates = [("数据集检查", "50 条样本通过", CYAN), ("单批前后向", "损失与梯度非零", ORANGE), ("完整训练", "59 步退出码为零", PINK), ("适配器重载", "新进程可加载", (115, 164, 255))]
    for i, (title, body, color) in enumerate(gates):
        x = 45 + i * 235
        d.rounded_rectangle((x, 180, x + 205, 500), radius=20, fill=(15, 24, 38), outline=color, width=5)
        d.ellipse((x + 64, 220, x + 141, 297), fill=color)
        d.text((x + 89, 230), "✓", fill=BG, font=font(48))
        draw_wrapped(d, (x + 22, 335), title, font(26), WHITE, 160, spacing=5)
        draw_wrapped(d, (x + 22, 400), body, font(22), MUTED, 160, spacing=4)
        if i < 3:
            d.polygon([(x + 213, 330), (x + 232, 340), (x + 213, 350)], fill=MUTED)
    canvas.save(out, quality=94)


def chart_evidence(out: Path) -> None:
    canvas = Image.new("RGB", (980, 700), PANEL)
    d = ImageDraw.Draw(canvas)
    d.text((36, 26), "一条结果，如何被复核", fill=WHITE, font=font(38))
    steps = [("运行编号", "本次实验唯一标识", CYAN), ("配置与命令", "模型、代码、参数", ORANGE), ("日志与媒体", "截图、动图、视频", PINK), ("哈希与指标", "文件一致、数字唯一", (115, 164, 255))]
    x0 = 70
    for i, (title, body, color) in enumerate(steps):
        x = x0 + i * 225
        d.rounded_rectangle((x, 180, x + 185, 510), radius=18, fill=(15, 24, 38), outline=color, width=4)
        d.rectangle((x + 55, 235, x + 130, 325), outline=color, width=5)
        d.line((x + 75, 260, x + 112, 260), fill=WHITE, width=3)
        d.line((x + 75, 280, x + 112, 280), fill=WHITE, width=3)
        d.line((x + 75, 300, x + 105, 300), fill=WHITE, width=3)
        draw_wrapped(d, (x + 18, 365), title, font(26), WHITE, 150, spacing=5)
        draw_wrapped(d, (x + 18, 430), body, font(22), MUTED, 150, spacing=4)
        if i < 3:
            d.polygon([(x + 191, 330), (x + 218, 340), (x + 191, 350)], fill=MUTED)
    canvas.save(out, quality=94)


def chart_roadmap(out: Path) -> None:
    canvas = Image.new("RGB", (980, 700), PANEL)
    d = ImageDraw.Draw(canvas)
    d.text((36, 26), "下一轮的三步路线", fill=WHITE, font=font(38))
    steps = [("兼容资产", "让障碍投影稳定", CYAN), ("有效深度", "减少输入回退", ORANGE), ("目标数据", "提升目标相关训练", PINK)]
    for i, (title, body, color) in enumerate(steps):
        x = 85 + i * 290
        d.ellipse((x, 180, x + 120, 300), fill=(15, 24, 38), outline=color, width=6)
        d.text((x + 39, 210), str(i + 1), fill=color, font=font(48))
        d.line((x + 60, 300, x + 60, 385), fill=color, width=6)
        d.polygon([(x + 49, 375), (x + 60, 400), (x + 71, 375)], fill=color)
        draw_wrapped(d, (x - 20, 430), title, font(30), WHITE, 160, spacing=6)
        draw_wrapped(d, (x - 20, 500), body, font(22), MUTED, 170, spacing=4)
        if i < 2:
            d.line((x + 125, 240, x + 250, 240), fill=MUTED, width=4)
            d.polygon([(x + 245, 230), (x + 270, 240), (x + 245, 250)], fill=MUTED)
    canvas.save(out, quality=94)


def make_charts(metrics: dict, plots: Path) -> dict[str, Path]:
    plots.mkdir(parents=True, exist_ok=True)
    paths = {
        "metrics": plots / "metrics-base-lora.png",
        "distance": plots / "episode-distance.png",
        "actions": plots / "action-counts.png",
        "schema": plots / "schema-sidecar.png",
        "lora": plots / "lora-config.png",
        "gates": plots / "validation-gates.png",
        "evidence": plots / "evidence-chain.png",
        "roadmap": plots / "next-roadmap.png",
    }
    chart_base_lora(metrics, paths["metrics"])
    chart_episode_distance(metrics, paths["distance"])
    chart_actions(metrics, paths["actions"])
    chart_schema(paths["schema"])
    chart_lora(paths["lora"])
    chart_gates(paths["gates"])
    chart_evidence(paths["evidence"])
    chart_roadmap(paths["roadmap"])
    return paths


def visual_image(path: Path, kind: str) -> Image.Image:
    image = Image.open(path).convert("RGB")
    if kind == "photo":
        return ImageOps.fit(image, (980, 700), method=Image.Resampling.LANCZOS)
    return ImageOps.contain(image, (980, 700), method=Image.Resampling.LANCZOS)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--metrics", type=Path, default=ROOT / "experiments/exp02-equivalent-v3/eval_result.json")
    parser.add_argument("--ai-dir", type=Path, default=ROOT / "assets/ai-diagrams")
    parser.add_argument("--plots-dir", type=Path, default=ROOT / "assets/plots")
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    out = args.out_dir.expanduser().resolve()
    ai = args.ai_dir.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    metrics = load_metric(args.metrics.expanduser().resolve())
    plots = make_charts(metrics, args.plots_dir.expanduser().resolve())

    def photo(name: str) -> tuple[Path, str]:
        return source / name, "photo"

    def diagram(name: str) -> tuple[Path, str]:
        return ai / name, "diagram"

    def plot(name: str) -> tuple[Path, str]:
        return plots[name], "plot"

    base = summary(metrics, "base_model")
    lora = summary(metrics, "lora_model")
    cards = [
        ("一句话，能不能变成动作？", "我给机器人一句指令：走向红色目标，然后停下。真正要验证的，不是画面好不好看，而是模型输出能不能一路进入真实仿真。", photo("train-1001-start.jpg"), False),
        ("先说清楚：这是非官方实验", "流程参考课程指南，但没有课程私有适配包；这里展示的是自采等价资产与独立闭环，不是课程原样复现，也不提交课程榜单。", photo("eval-2001-start.jpg"), False),
        ("场景、机器人、相机", "实验使用室内市场场景、G2 刚体导航代理和头部相机。它用于验证视觉语言导航闭环，不宣称真实人形步态。", photo("train-1025-mid.jpg"), False),
        ("感知 → 模型 → 动作", "这张是人工智能生成的结构示意图；真实证据仍来自实验截图和日志。彩色图、深度图、位姿进入模型，再输出离散动作。", diagram("ai-01-perception-action.png"), True),
        ("动作空间被固定为四个", "停止、前进 0.25 米、左转 15 度、右转 15 度。后退只在 Stage 0 调试端出现，不进入训练动作。", photo("stage0-forward-after.jpg"), False),
        ("每次移动后，等两个渲染帧", "动作提交后先等待至少两个渲染帧，再保存彩色图、深度图、位姿、碰撞和目标距离，避免把上一帧误当成新结果。", photo("stage0-after-block.jpg"), False),
        ("数据不是一张图，而是一条流水线", "人工智能生成示意图只解释结构：红色目标、相机采集、轨迹文件、低秩适配、留出评测。关键字段仍由真实采集器写入。", diagram("ai-02-data-pipeline.png"), True),
        ("数据拆分：3 + 50 + 10", "先用 3 条冒烟轨迹验证接口，再采固定种子 1001–1050 的 50 条训练轨迹和 2001–2010 的 10 条评测轨迹；严格校验为 50/50 与 10/10。", photo("train-1050-mid.jpg"), False),
        ("公开标注和旁路记录各司其职", "公开标注保持兼容格式：首动作为 -1，不放最终停止；深度、完整停止、轨迹、碰撞和目标信息放入旁路记录。", plot("schema"), False),
        ("真正的闭环：模型自己发动作", "人工智能生成示意图对应真实执行顺序：指令 → 观测 → 模型 → 本机接口 → 仿真环境 → 指标，再把下一帧送回模型。", diagram("ai-03-closed-loop.png"), True),
        ("服务只监听本机回环地址", "采集线程只提交请求，仿真动作回到主线程执行；近障碍由真实 head depth 安全门拒绝，并记录位姿不变。", photo("stage0-before-block.jpg"), False),
        ("低秩适配到底改了什么？", "配置固定为秩 8、缩放 16、丢弃率 0.05、1 轮、批量 1、学习率 0.00002、脑浮点和梯度检查点。", plot("lora"), False),
        ("训练通过，不等于模型会导航", "四道门全部通过：50/50 数据检查、单批非零 loss/梯度、59 个真实更新步、适配器新进程重载。训练 loss 从 0.4167 到 0.0823，但最终仍要看闭环。", plot("gates"), False),
        ("同一批十条，基础模型没有过半米线", f"基础模型半米成功率 {base['success_0_5']}/10，三米成功率 {base['success_3']}/10，平均最终距离 {base['mean_final_distance_to_goal']:.2f} 米，碰撞 {base['collisions']} 次。", plot("metrics"), False),
        ("低秩适配也没有过半米线", f"低秩适配半米成功率 {lora['success_0_5']}/10，三米成功率 {lora['success_3']}/10，平均最终距离 {lora['mean_final_distance_to_goal']:.2f} 米，碰撞 {lora['collisions']} 次。", plot("distance"), False),
        ("动作统计也要公开", "不是只展示一条轨迹：下面汇总十条留出评测中停止、前进、左转、右转的总次数，基础模型和低秩适配都按同一批样本计算。", plot("actions"), False),
        ("失败不是一句‘以后再说’", "人工智能示意图用于解释缺口：课程私有 AABB 工具不可得，公开资产遍历会触发仿真退出；本轮用可审计的 head-depth 安全门完成等价碰撞保护。", diagram("ai-04-failure-roadmap.png"), True),
        ("每个数字都能回到证据链", "运行编号、源码和模型修订、配置、命令、日志、截图、视频、文件哈希和唯一指标源都写入实验清单，便于复核而不是靠口述。", plot("evidence"), False),
        ("下一轮先补三件事", "第一，换可稳定投影 AABB 的兼容资产；第二，让红色目标在更多训练视角中清晰可见；第三，增加目标相关训练覆盖。仍复用同一批十条回归。", plot("roadmap"), False),
        ("最终结果：成功率为零，但闭环是真的", f"半米成功率：基础模型 {base['success_0_5']}/10，低秩适配 {lora['success_0_5']}/10。失败不包装成成功；模型→接口→仿真→安全门→指标完整留痕。", photo("stage3-base-2004-end.jpg"), False),
    ]
    assert len(cards) == 20
    title_font, body_font, small_font = font(50), font(28), font(25)
    for index, (title, body, (visual, kind), ai_label) in enumerate(cards, 1):
        canvas = Image.new("RGB", (1080, 1440), BG)
        image = visual_image(visual, kind)
        x = (1080 - image.width) // 2
        y = 180 + (700 - image.height) // 2
        canvas.paste(image, (x, y))
        d = ImageDraw.Draw(canvas)
        d.text((50, 45), f"{index:02d}/20  视觉语言导航实验", fill=ORANGE, font=small_font)
        d.text((50, 975), title, fill=WHITE, font=title_font)
        d.rounded_rectangle((42, 1065, 1038, 1295), radius=20, fill=PANEL)
        draw_wrapped(d, (75, 1115), body, body_font, WHITE, 930, spacing=8)
        if ai_label:
            d.rounded_rectangle((760, 205, 1025, 255), radius=14, fill=(33, 47, 63), outline=CYAN, width=2)
            d.text((785, 216), "人工智能示意图", fill=CYAN, font=font(22))
        d.text((50, 1360), "非官方 · 非商业研究演示 · 不提交榜单", fill=MUTED, font=small_font)
        canvas.save(out / f"carousel-{index:02d}.jpg", quality=93, optimize=True)
    print(f"generated {len(cards)} cards in {out}")


if __name__ == "__main__":
    main()
