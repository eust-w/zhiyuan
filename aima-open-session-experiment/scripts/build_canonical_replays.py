"""Build Chinese, metric-annotated replays for the canonical paired evaluation.

The private input bundle contains one 2 fps MP4 per model/episode plus the
source ``eval_result.json``.  Public outputs contain only the camera replay and
safe evaluation fields: action, target distance, blocked/collision state and a
mini trajectory map.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ACTION_LABELS = {-1: "初始帧", 0: "停止", 1: "前进", 2: "左转", 3: "右转"}
VARIANT_LABELS = {"base": "基础模型", "lora": "LoRA 模型"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def expanded_actions(predictions: list[dict[str, Any]], observation_count: int) -> list[int]:
    """Align queued model actions to the observation produced after each step."""
    actions = [-1] * observation_count
    for prediction in predictions:
        start = int(prediction.get("step_id", 0)) + 1
        for offset, action in enumerate(prediction.get("actions", [])):
            index = start + offset
            if 0 <= index < observation_count:
                actions[index] = int(action)
    return actions


def _pose_xy(observation: dict[str, Any]) -> tuple[float, float]:
    matrix = observation.get("pose_matrix") or [0.0] * 16
    return float(matrix[3]), float(matrix[7])


def _map_point(
    point: tuple[float, float],
    bounds: tuple[float, float, float, float],
    box: tuple[int, int, int, int],
) -> tuple[int, int]:
    min_x, max_x, min_y, max_y = bounds
    left, top, right, bottom = box
    span_x = max(max_x - min_x, 1e-6)
    span_y = max(max_y - min_y, 1e-6)
    x = left + int((point[0] - min_x) / span_x * (right - left))
    y = bottom - int((point[1] - min_y) / span_y * (bottom - top))
    return x, y


def render_dashboard(
    frame: np.ndarray,
    *,
    observations: list[dict[str, Any]],
    actions: list[int],
    frame_index: int,
    variant: str,
    episode_id: str,
) -> np.ndarray:
    """Add a safe Chinese dashboard and trajectory map to one BGR frame."""
    output = frame.copy()
    height, width = output.shape[:2]
    index = min(max(frame_index, 0), len(observations) - 1)
    observation = observations[index]
    action_id = actions[index] if index < len(actions) else -1

    shade = output.copy()
    cv2.rectangle(shade, (24, 22), (min(width - 24, 660), 210), (7, 17, 29), -1)
    map_box = (max(24, width - 294), max(238, height - 270), width - 24, height - 24)
    cv2.rectangle(shade, (map_box[0] - 12, map_box[1] - 42), (map_box[2] + 12, map_box[3] + 12), (7, 17, 29), -1)
    output = cv2.addWeighted(shade, 0.84, output, 0.16, 0)

    path = [_pose_xy(item) for item in observations]
    target_values = observation.get("target_xy") or [path[-1][0], path[-1][1]]
    target = (float(target_values[0]), float(target_values[1]))
    xs = [point[0] for point in path] + [target[0]]
    ys = [point[1] for point in path] + [target[1]]
    margin_x = max((max(xs) - min(xs)) * 0.08, 0.2)
    margin_y = max((max(ys) - min(ys)) * 0.08, 0.2)
    bounds = (min(xs) - margin_x, max(xs) + margin_x, min(ys) - margin_y, max(ys) + margin_y)
    mapped = [_map_point(point, bounds, map_box) for point in path[: index + 1]]
    if len(mapped) > 1:
        cv2.polylines(output, [np.array(mapped, dtype=np.int32)], False, (238, 204, 77), 3, cv2.LINE_AA)
    if mapped:
        cv2.circle(output, mapped[-1], 7, (238, 204, 77), -1, cv2.LINE_AA)
    cv2.circle(output, _map_point(target, bounds, map_box), 8, (72, 72, 245), -1, cv2.LINE_AA)

    rgb = cv2.cvtColor(output, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(rgb)
    draw = ImageDraw.Draw(image)
    blocked = "是" if observation.get("blocked") else "否"
    collision = "是" if observation.get("collision") else "否"
    distance = float(observation.get("distance_to_goal_m", 0.0))
    variant_label = VARIANT_LABELS.get(variant, variant)
    lines = [
        (f"真实录屏 · {variant_label} · {episode_id}", 30, (245, 174, 80)),
        (f"步数：{index:03d}/{max(len(observations) - 1, 0):03d}", 27, (244, 248, 255)),
        (f"动作：{ACTION_LABELS.get(action_id, '未知')}（{action_id}）", 27, (244, 248, 255)),
        (f"目标距离：{distance:.3f} 米", 27, (244, 248, 255)),
        (f"受阻：{blocked}    碰撞：{collision}", 27, (244, 248, 255)),
    ]
    y = 42
    for text, size, color in lines:
        draw.text((46, y), text, font=font(size), fill=color)
        y += 34
    draw.text((map_box[0], map_box[1] - 36), "实时轨迹（红点为目标）", font=font(24), fill=(244, 248, 255))
    return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def _detail_map(eval_data: dict[str, Any], variant: str) -> dict[str, dict[str, Any]]:
    key = "base_model" if variant == "base" else "lora_model"
    details = eval_data[key]["model_evaluation"]["summary"]["episodes_detail"]
    return {str(detail["episode_id"]): detail for detail in details}


def annotate_video(source: Path, output: Path, detail: dict[str, Any], variant: str) -> dict[str, Any]:
    observations = list(detail["observations"])
    actions = expanded_actions(list(detail.get("predictions", [])), len(observations))
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open source replay: {source.name}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 2.0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="canonical-replay-") as temp:
        intermediate = Path(temp) / "annotated.mp4"
        writer = cv2.VideoWriter(str(intermediate), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        frame_count = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            writer.write(
                render_dashboard(
                    frame,
                    observations=observations,
                    actions=actions,
                    frame_index=frame_count,
                    variant=variant,
                    episode_id=str(detail["episode_id"]),
                )
            )
            frame_count += 1
        capture.release()
        writer.release()
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(intermediate),
                "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", str(output),
            ],
            check=True,
        )
    if frame_count != len(observations):
        raise ValueError(f"{detail['episode_id']}: video frames {frame_count} != observations {len(observations)}")
    return {
        "episode_id": detail["episode_id"],
        "variant": variant,
        "frame_count": frame_count,
        "duration_s": frame_count / fps,
        "success_0_5": bool(detail["success_0_5"]),
        "spl_0_5": float(detail["spl_0_5"]),
        "final_distance_to_goal": float(detail["final_distance_to_goal"]),
        "min_distance_to_goal": float(detail["min_distance_to_goal"]),
        "collisions": int(detail["collisions"]),
        "action_counts": detail["action_counts"],
        "output": output.relative_to(ROOT).as_posix(),
        "sha256": sha256(output),
    }


def build_all(bundle_dir: Path, eval_path: Path, output_dir: Path) -> dict[str, Any]:
    bundled_eval = bundle_dir / "eval_result.json"
    if sha256(bundled_eval) != sha256(eval_path):
        raise ValueError("downloaded canonical eval_result.json does not match the repository metric source")
    eval_data = json.loads(eval_path.read_text(encoding="utf-8"))
    media: list[dict[str, Any]] = []
    for variant, prefix in (("base", "model-base-exp02baseguard-"), ("lora", "model-lora-exp02loraguard-")):
        details = _detail_map(eval_data, variant)
        for episode_id in eval_data["heldout_episode_ids"]:
            source = bundle_dir / f"{prefix}{episode_id}.mp4"
            output = output_dir / f"{variant}-{episode_id}-annotated.mp4"
            media.append(annotate_video(source, output, details[episode_id], variant))
    report = {
        "schema_version": "aima-vln-canonical-replays/v1",
        "status": "passed",
        "metric_source": eval_path.relative_to(ROOT).as_posix(),
        "metric_source_sha256": sha256(eval_path),
        "heldout_episode_ids": eval_data["heldout_episode_ids"],
        "media": media,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        default=ROOT / "assets/series/recapture/raw/canonical-full-bundle/canonical-full",
    )
    parser.add_argument(
        "--eval",
        type=Path,
        default=ROOT / "experiments/exp02-equivalent-v3/eval_result.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "assets/series/recapture/canonical",
    )
    args = parser.parse_args()
    print(json.dumps(build_all(args.bundle_dir.resolve(), args.eval.resolve(), args.output_dir.resolve()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
