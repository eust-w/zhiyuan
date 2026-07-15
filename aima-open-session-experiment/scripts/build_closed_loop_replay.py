"""Annotate a real closed-loop RGB replay with per-step model evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ACTION_NAMES = {0: "停止", 1: "前进", 2: "左转", 3: "右转"}


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


def extract_replay_steps(payload: dict[str, Any]) -> dict[str, Any]:
    detail = payload["summary"]["episodes_detail"][0]
    actions = [int(action) for prediction in detail["predictions"] for action in prediction["actions"]]
    observations = detail["observations"]
    if len(actions) != len(observations) - 1:
        raise ValueError(f"action/observation mismatch: {len(actions)} actions for {len(observations)} observations")
    steps: list[dict[str, Any]] = []
    for index, observation in enumerate(observations):
        pose = observation["pose_matrix"]
        steps.append(
            {
                "step_id": int(observation["step_id"]),
                "action_id": None if index == 0 else actions[index - 1],
                "distance_to_goal_m": float(observation["distance_to_goal_m"]),
                "blocked": bool(observation.get("blocked", False)),
                "collision": bool(observation.get("collision", False)),
                "xy": [float(pose[3]), float(pose[7])],
            }
        )
    return {
        "variant": payload.get("variant", detail.get("model_variant", "model")),
        "episode_id": detail["source_episode_id"],
        "target_xy": [float(value) for value in observations[0]["target_xy"]],
        "steps": steps,
    }


def _map_point(point: list[float], bounds: tuple[float, float, float, float], box: tuple[int, int, int, int]) -> tuple[int, int]:
    min_x, max_x, min_y, max_y = bounds
    left, top, right, bottom = box
    x = left + int((point[0] - min_x) / max(max_x - min_x, 1e-6) * (right - left))
    y = bottom - int((point[1] - min_y) / max(max_y - min_y, 1e-6) * (bottom - top))
    return x, y


def annotate_frame(frame: Image.Image, replay: dict[str, Any], index: int) -> Image.Image:
    canvas = frame.convert("RGBA")
    draw = ImageDraw.Draw(canvas, "RGBA")
    width, height = canvas.size
    step = replay["steps"][index]
    title_font = _font(34)
    body_font = _font(30)
    small_font = _font(24)

    draw.rounded_rectangle((42, 38, 710, 104), radius=18, fill=(8, 18, 30, 225))
    draw.text((68, 54), f"真实录屏｜{replay['variant']} 模型闭环", font=title_font, fill=(245, 174, 80, 255))
    draw.rounded_rectangle((width - 520, 38, width - 42, 104), radius=18, fill=(8, 18, 30, 225))
    draw.text((width - 490, 56), f"episode：{replay['episode_id']}", font=body_font, fill=(231, 240, 250, 255))

    draw.rounded_rectangle((42, height - 190, width - 42, height - 38), radius=24, fill=(8, 18, 30, 232))
    action_id = step["action_id"]
    action_label = "RESET" if action_id is None else f"{action_id} {ACTION_NAMES.get(action_id, '非法动作')}"
    blocked = "是" if step["blocked"] else "否"
    collision = "是" if step["collision"] else "否"
    line = (
        f"step {step['step_id']:02d}/{len(replay['steps']) - 1:02d}  ·  动作 {action_label}  ·  "
        f"目标距离 {step['distance_to_goal_m']:.3f}m  ·  blocked {blocked}  ·  碰撞 {collision}"
    )
    draw.text((76, height - 157), line, font=body_font, fill=(240, 246, 252, 255))
    draw.text((76, height - 96), "动作由 StreamVLN generate 输出；轨迹与距离来自 GenieSim adapter 响应", font=small_font, fill=(170, 193, 216, 255))

    panel = (width - 470, 138, width - 42, 430)
    draw.rounded_rectangle(panel, radius=20, fill=(8, 18, 30, 218), outline=(66, 94, 120, 230), width=2)
    draw.text((panel[0] + 22, panel[1] + 18), "轨迹俯视图", font=body_font, fill=(231, 240, 250, 255))
    map_box = (panel[0] + 28, panel[1] + 72, panel[2] - 28, panel[3] - 26)
    all_points = [item["xy"] for item in replay["steps"]] + [replay["target_xy"]]
    xs = [point[0] for point in all_points]
    ys = [point[1] for point in all_points]
    pad_x = max((max(xs) - min(xs)) * 0.15, 0.25)
    pad_y = max((max(ys) - min(ys)) * 0.15, 0.25)
    bounds = (min(xs) - pad_x, max(xs) + pad_x, min(ys) - pad_y, max(ys) + pad_y)
    mapped = [_map_point(item["xy"], bounds, map_box) for item in replay["steps"]]
    if len(mapped) > 1:
        draw.line(mapped, fill=(101, 120, 140, 150), width=5)
    if index > 0:
        draw.line(mapped[: index + 1], fill=(77, 204, 238, 255), width=8)
    current = mapped[index]
    target = _map_point(replay["target_xy"], bounds, map_box)
    draw.ellipse((current[0] - 10, current[1] - 10, current[0] + 10, current[1] + 10), fill=(245, 174, 80, 255))
    draw.ellipse((target[0] - 11, target[1] - 11, target[0] + 11, target[1] + 11), fill=(235, 78, 91, 255))
    draw.text((target[0] + 13, target[1] - 16), "目标", font=small_font, fill=(255, 164, 174, 255))
    return canvas.convert("RGB")


def build_replay(source: Path, evidence: Path, output: Path) -> None:
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    replay = extract_replay_steps(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="aima-closed-loop-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(source),
                "-vf",
                "fps=2",
                str(temp_dir / "source-%04d.png"),
            ],
            check=True,
        )
        frames = sorted(temp_dir.glob("source-*.png"))
        if len(frames) != len(replay["steps"]):
            raise ValueError(f"video/evidence mismatch: {len(frames)} frames for {len(replay['steps'])} steps")
        for index, frame_path in enumerate(frames):
            annotated = annotate_frame(Image.open(frame_path), replay, index)
            annotated.save(temp_dir / f"annotated-{index + 1:04d}.png")
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-framerate",
                "2",
                "-i",
                str(temp_dir / "annotated-%04d.png"),
                "-r",
                "30",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "19",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(output),
            ],
            check=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build_replay(args.source, args.evidence, args.output)


if __name__ == "__main__":
    main()
