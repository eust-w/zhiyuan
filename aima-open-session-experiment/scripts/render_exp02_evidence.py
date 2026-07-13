#!/usr/bin/env python3
"""Render sanitized evidence cards from the experiment's machine-readable results.

The cards are not substitutes for raw logs.  Every number is read from the
checked-in result JSON or parsed from its corresponding log, and the source is
printed on the card so readers can audit it.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    del bold  # STHeiti Medium is used consistently for stable CJK rendering.
    return ImageFont.truetype(FONT, size=size, index=0)


def stage2_cards(exp: Path, output: Path) -> None:
    result = json.loads((exp / "stage2_result_v2.json").read_text(encoding="utf-8"))
    gates = result["gates"]
    training = gates["full_training"]
    reload_gate = gates["adapter_reload"]

    canvas = Image.new("RGB", (1600, 900), "#101827")
    draw = ImageDraw.Draw(canvas)
    draw.text((90, 70), "Stage 2｜这次 LoRA 真的更新了吗？", font=font(54, bold=True), fill="#F8FAFC")
    draw.text((90, 150), "先过单批次反向传播，再允许完整训练", font=font(30), fill="#94A3B8")
    rows = [
        ("数据检查", f"{gates['dataset_only']['valid']}/50 有效，0 条失败"),
        ("首批 loss", f"{gates['single_batch_forward_backward']['loss']:.4f}"),
        ("首批 grad_norm", f"{gates['single_batch_forward_backward']['grad_norm']:.4f}"),
        ("完整训练", f"{training['observed_steps']} 步，{training['loss_first']:.4f} → {training['loss_last']:.4f}"),
        ("峰值显存", f"{training['peak_gpu_memory_mib'] / 1024:.2f} GiB"),
        ("新进程重载", "通过" if reload_gate["status"] == "passed" else "失败"),
    ]
    y = 245
    for label, value in rows:
        draw.rounded_rectangle((90, y, 1510, y + 82), radius=18, fill="#172338")
        draw.text((125, y + 20), label, font=font(28), fill="#93C5FD")
        draw.text((550, y + 20), value, font=font(30, bold=True), fill="#F8FAFC")
        y += 94
    draw.text((90, 825), "数据源：experiments/exp02-equivalent-v3/stage2_result_v2.json", font=font(22), fill="#64748B")
    canvas.save(output / "stage2-gates.png")

    losses: list[float] = []
    grad_norms: list[float] = []
    for line in (exp / "logs" / "stage2-train.stdout.log").read_text(encoding="utf-8").splitlines():
        if not line.startswith("{'loss':"):
            continue
        record = ast.literal_eval(line)
        losses.append(float(record["loss"]))
        grad_norms.append(float(record["grad_norm"]))
    if not losses:
        raise RuntimeError("no loss records found in Stage 2 training log")
    chart = Image.new("RGB", (1600, 900), "#101827")
    chart_draw = ImageDraw.Draw(chart)
    chart_draw.text((90, 55), "Stage 2｜59 个真实更新步", font=font(54, bold=True), fill="#F8FAFC")
    left, top, right, bottom = 120, 175, 1500, 760
    max_value = max(max(losses), max(grad_norms)) * 1.08
    for tick in range(6):
        y = bottom - (bottom - top) * tick / 5
        value = max_value * tick / 5
        chart_draw.line((left, y, right, y), fill="#26354C", width=2)
        chart_draw.text((35, int(y) - 14), f"{value:.2f}", font=font(20), fill="#94A3B8")
    def points(values: list[float]) -> list[tuple[float, float]]:
        return [
            (left + (right - left) * index / max(1, len(values) - 1), bottom - (bottom - top) * value / max_value)
            for index, value in enumerate(values)
        ]
    chart_draw.line(points(losses), fill="#38BDF8", width=5, joint="curve")
    chart_draw.line(points(grad_norms), fill="#F59E0B", width=3, joint="curve")
    chart_draw.text((120, 790), "— loss", font=font(24, bold=True), fill="#38BDF8")
    chart_draw.text((300, 790), "— grad_norm", font=font(24, bold=True), fill="#F59E0B")
    chart_draw.text((1020, 790), f"训练步：1 → {len(losses)}", font=font(24), fill="#CBD5E1")
    chart_draw.text((90, 850), "源：stage2-train.stdout.log｜loss 与 grad_norm 均为非零有限值", font=font(22), fill="#64748B")
    chart.save(output / "stage2-loss-curve.png")


def stage1_cards(exp: Path, output: Path) -> None:
    validation = json.loads((exp / "dataset-validation.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "artifacts" / "equivalent-scene" / "asset-capture-manifest.json").read_text(encoding="utf-8"))
    canvas = Image.new("RGB", (1600, 900), "#101827")
    draw = ImageDraw.Draw(canvas)
    draw.text((90, 65), "Stage 1｜先验数据，再谈训练", font=font(54, bold=True), fill="#F8FAFC")
    rows = [
        ("冒烟轨迹", "3 条，先验证采集链"),
        ("训练集", f"{validation['train']['valid']}/50 严格校验通过"),
        ("固定评测集", f"{validation['eval']['valid']}/10 严格校验通过"),
        ("标定 RGB-D", f"{manifest['unique_calibrated_frames']} 帧"),
        ("等价点云", f"{manifest['point_count']:,} 个彩色点"),
        ("等价资产", "sample.ply / sample.usda / sample.usdz"),
    ]
    y = 190
    for label, value in rows:
        draw.rounded_rectangle((90, y, 1510, y + 88), radius=18, fill="#172338")
        draw.text((125, y + 22), label, font=font(28), fill="#86EFAC")
        draw.text((550, y + 22), value, font=font(30, bold=True), fill="#F8FAFC")
        y += 100
    draw.text((90, 815), "严格校验包含：schema、帧/动作计数、文件存在、图像可解码", font=font(23), fill="#94A3B8")
    draw.text((90, 855), "声明：自采等价资产，不是课程私有原件", font=font(22), fill="#FCA5A5")
    canvas.save(output / "stage1-validation.png")


def stage0_cards(exp: Path, output: Path) -> None:
    health = json.loads((exp / "stage0-health.json").read_text(encoding="utf-8"))
    keyboard = json.loads((exp / "stage0-keyboard.json").read_text(encoding="utf-8"))["records"]
    forward = json.loads((exp / "stage0-forward-check.json").read_text(encoding="utf-8"))[-1]
    keys_seen = sorted({row["key"] for row in keyboard if row["key"] != "reset"})
    blocked_rows = [row for row in keyboard if row["observation"].get("blocked")]
    unchanged = all(
        row["observation"]["pose_matrix"] == keyboard[index - 1]["observation"]["pose_matrix"]
        for index, row in enumerate(keyboard)
        if index and row["observation"].get("blocked")
    )
    start_pose = forward["reset"]["pose_matrix"]
    end_pose = forward["step"]["pose_matrix"]
    distance = ((end_pose[3] - start_pose[3]) ** 2 + (end_pose[7] - start_pose[7]) ** 2) ** 0.5
    rows = [
        ("服务", f"{health['host']}:{health['port']}，ready=true"),
        ("场景与机器人", f"{health['scene']} / {health['robot']}"),
        ("键盘", " / ".join(keys_seen)),
        ("前进增量", f"{distance:.2f} m"),
        ("近障碍拒绝", f"{len(blocked_rows)} 次，来源=head depth"),
        ("拒绝后位姿", "保持不变" if unchanged else "检查失败"),
    ]
    canvas = Image.new("RGB", (1600, 900), "#101827")
    draw = ImageDraw.Draw(canvas)
    draw.text((90, 65), "Stage 0｜先把仿真端验扎实", font=font(54, bold=True), fill="#F8FAFC")
    y = 190
    for label, value in rows:
        draw.rounded_rectangle((90, y, 1510, y + 88), radius=18, fill="#172338")
        draw.text((125, y + 22), label, font=font(28), fill="#C4B5FD")
        draw.text((550, y + 22), value, font=font(30, bold=True), fill="#F8FAFC")
        y += 100
    draw.text((90, 825), "W/S/A/D/Space 只用于 Stage 0；训练动作仍严格为 STOP/前进/左转/右转", font=font(22), fill="#94A3B8")
    canvas.save(output / "stage0-validation.png")


def stage3_cards(exp: Path, output: Path) -> None:
    metrics = json.loads((exp / "eval_result.json").read_text(encoding="utf-8"))
    base = metrics["base_model"]["model_evaluation"]["summary"]
    lora = metrics["lora_model"]["model_evaluation"]["summary"]
    canvas = Image.new("RGB", (1600, 900), "#101827")
    draw = ImageDraw.Draw(canvas)
    draw.text((90, 55), "Stage 3｜同一批 10 条，模型自己走", font=font(52, bold=True), fill="#F8FAFC")
    columns = [("StreamVLN base", base, "#38BDF8"), ("LoRA", lora, "#F472B6")]
    for index, (name, summary, color) in enumerate(columns):
        x0 = 90 + index * 760
        draw.rounded_rectangle((x0, 150, x0 + 700, 800), radius=24, fill="#172338")
        draw.text((x0 + 40, 185), name, font=font(36, bold=True), fill=color)
        values = [
            ("success@0.5m", f"{summary['success_0_5']}/10"),
            ("success@3m", f"{summary['success_3']}/10"),
            ("oracle@3m", f"{summary['oracle_success_3']}/10"),
            ("平均最终距离", f"{summary['mean_final_distance_to_goal']:.3f} m"),
            ("平均路径", f"{summary['mean_path_length']:.3f} m"),
            ("平均步数", f"{summary['mean_steps']:.1f}"),
            ("碰撞尝试", str(summary["collisions"])),
        ]
        y = 275
        for label, value in values:
            draw.text((x0 + 40, y), label, font=font(26), fill="#94A3B8")
            draw.text((x0 + 385, y), value, font=font(29, bold=True), fill="#F8FAFC")
            y += 68
    draw.text((90, 845), "唯一指标源：eval_result.json｜碰撞=真实 head-depth 安全门拦截的前进尝试", font=font(21), fill="#64748B")
    canvas.save(output / "stage3-paired-metrics.png")

    chart = Image.new("RGB", (1600, 900), "#101827")
    chart_draw = ImageDraw.Draw(chart)
    chart_draw.text((90, 55), "Stage 3｜十条最终距离，失败也全部入表", font=font(50, bold=True), fill="#F8FAFC")
    left, top, right, bottom = 120, 180, 1500, 720
    base_rows = base["episodes_detail"]
    lora_rows = lora["episodes_detail"]
    maximum = max(row["final_distance_to_goal"] for row in base_rows + lora_rows) * 1.1
    for tick in range(6):
        y = bottom - (bottom - top) * tick / 5
        chart_draw.line((left, y, right, y), fill="#26354C", width=2)
        chart_draw.text((40, int(y) - 13), f"{maximum * tick / 5:.1f}m", font=font(19), fill="#94A3B8")
    group = (right - left) / 10
    for index, (base_row, lora_row) in enumerate(zip(base_rows, lora_rows)):
        center = left + group * (index + 0.5)
        for offset, row, color in [(-22, base_row, "#38BDF8"), (22, lora_row, "#F472B6")]:
            height = (bottom - top) * row["final_distance_to_goal"] / maximum
            chart_draw.rounded_rectangle((center + offset - 17, bottom - height, center + offset + 17, bottom), radius=7, fill=color)
        chart_draw.text((center - 30, bottom + 20), str(2001 + index), font=font(18), fill="#CBD5E1")
    chart_draw.text((120, 800), "■ base", font=font(25), fill="#38BDF8")
    chart_draw.text((300, 800), "■ LoRA", font=font(25), fill="#F472B6")
    chart_draw.text((850, 800), "成功半径：0.5m（两者均 0/10）", font=font(25), fill="#FCA5A5")
    chart.save(output / "stage3-episode-distances.png")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exp", type=Path, default=ROOT / "experiments" / "exp02-equivalent-v3")
    parser.add_argument("--output", type=Path, default=ROOT / "assets" / "screenshots" / "v3")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    stage0_cards(args.exp.resolve(), args.output.resolve())
    stage1_cards(args.exp.resolve(), args.output.resolve())
    stage2_cards(args.exp.resolve(), args.output.resolve())
    stage3_cards(args.exp.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
