"""Verify the four publishable 10-minute tutorial masters."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

try:
    from scripts.series_manifest import load_manifest, metric_snapshot
    from scripts.verify_series_media import probe, public_media_path, scan_sensitive, subtitle_errors
except ModuleNotFoundError:
    from series_manifest import load_manifest, metric_snapshot
    from verify_series_media import probe, public_media_path, scan_sensitive, subtitle_errors


ROOT = Path(__file__).resolve().parents[1]


def validate_storyboard(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    episodes = manifest.get("episodes", [])
    if len(episodes) != 4:
        errors.append("storyboard must contain four episodes")
    target = float(manifest.get("real_ratio_target", 0.75))
    for episode in episodes:
        episode_id = episode.get("episode", "<missing>")
        segments = episode.get("segments", [])
        total = sum(float(segment.get("duration_s", 0)) for segment in segments)
        real = sum(
            float(segment.get("duration_s", 0))
            for segment in segments
            if segment.get("source_type") == "real_recording"
        )
        if not 600 <= total <= 900:
            errors.append(f"{episode_id}: duration outside 10-15 minutes: {total}")
        ratio = real / total if total else 0.0
        if ratio < target:
            errors.append(f"{episode_id}: real recording ratio {ratio:.3f} below {target:.3f}")
        for segment in segments:
            if segment.get("source_type") != "real_recording" and float(segment.get("duration_s", 0)) > 6:
                errors.append(f"{segment.get('segment_id')}: static segment exceeds 6 seconds")
    stage3 = next((item for item in episodes if item.get("episode") == "stage3"), {})
    canonical = [
        segment.get("source")
        for segment in stage3.get("segments", [])
        if "/recapture/canonical/" in str(segment.get("source", ""))
    ]
    if len(canonical) != 20 or len(set(canonical)) != 20:
        errors.append("stage3 must use 20 distinct canonical paired replays")
    return errors


def acceptance_status(media: list[dict[str, Any]], sensitive_hits: list[str]) -> str:
    if len(media) != 4 or sensitive_hits or not all(item.get("status") == "passed" for item in media):
        return "failed"
    return "passed"


def black_frame_hits(path: Path) -> list[str]:
    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-v", "info", "-i", str(path),
            "-vf", "blackdetect=d=1:pic_th=0.98", "-an", "-f", "null", "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return [line.strip() for line in result.stderr.splitlines() if "black_duration:" in line]


def loudness(path: Path) -> dict[str, float | None]:
    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-v", "info", "-i", str(path),
            "-filter_complex", "ebur128=peak=true", "-f", "null", "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    integrated = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s+LUFS", result.stderr)
    peak = re.findall(r"Peak:\s*(-?\d+(?:\.\d+)?)\s+dBFS", result.stderr)
    return {
        "integrated_lufs": float(integrated[-1]) if integrated else None,
        "true_peak_dbfs": float(peak[-1]) if peak else None,
    }


def validate_output(
    episode: dict[str, Any],
    media_root: Path,
    expected_metrics: dict[str, Any],
    project_root: Path,
    deep_media_checks: bool,
) -> dict[str, Any]:
    episode_id = episode["episode"]
    directory = media_root / episode_id
    video = directory / f"{episode_id}.mp4"
    srt = directory / f"{episode_id}.srt"
    media_manifest = directory / f"{episode_id}-media-manifest.json"
    errors: list[str] = []
    measured_loudness: dict[str, float | None] = {"integrated_lufs": None, "true_peak_dbfs": None}
    black_hits: list[str] = []
    if not video.is_file():
        errors.append("video missing")
        return {"episode": episode_id, "status": "failed", "errors": errors}
    if not srt.is_file():
        errors.append("SRT missing")
    else:
        errors.extend(subtitle_errors(srt))
    info = probe(video)
    streams = info.get("streams", [])
    video_stream = next((item for item in streams if item.get("codec_type") == "video"), {})
    audio_stream = next((item for item in streams if item.get("codec_type") == "audio"), {})
    duration = float(info.get("format", {}).get("duration", 0))
    if not 600 <= duration <= 900:
        errors.append(f"duration outside 10-15 minutes: {duration:.3f}")
    if (video_stream.get("codec_name"), video_stream.get("width"), video_stream.get("height"), video_stream.get("r_frame_rate")) != ("h264", 1920, 1080, "30/1"):
        errors.append("video must be H.264 1920x1080 30fps")
    if (audio_stream.get("codec_name"), audio_stream.get("sample_rate"), audio_stream.get("channels")) != ("aac", "48000", 2):
        errors.append("audio must be AAC 48kHz stereo")
    if not media_manifest.is_file():
        errors.append("media manifest missing")
    else:
        metadata = json.loads(media_manifest.read_text(encoding="utf-8"))
        if float(metadata.get("real_recording_ratio", 0)) < 0.75:
            errors.append("media manifest real recording ratio below 0.75")
        if metadata.get("metrics") != expected_metrics:
            errors.append("media manifest metrics do not match eval_result.json")
    if deep_media_checks:
        black_hits = black_frame_hits(video)
        if black_hits:
            errors.append("one-second black frame interval detected")
        measured_loudness = loudness(video)
        integrated = measured_loudness["integrated_lufs"]
        peak = measured_loudness["true_peak_dbfs"]
        if integrated is None or not -18 <= integrated <= -14:
            errors.append(f"integrated loudness outside -16±2 LUFS: {integrated}")
        if peak is None or peak > -0.5:
            errors.append(f"audio peak exceeds -0.5 dBFS: {peak}")
    return {
        "episode": episode_id,
        "video": public_media_path(video, project_root),
        "srt": public_media_path(srt, project_root),
        "duration_s": duration,
        "real_recording_ratio": sum(float(s["duration_s"]) for s in episode["segments"] if s["source_type"] == "real_recording") / sum(float(s["duration_s"]) for s in episode["segments"]),
        "loudness": measured_loudness,
        "black_frame_hits": black_hits,
        "status": "passed" if not errors else "failed",
        "errors": errors,
    }


def build_report(
    storyboard_path: Path,
    media_root: Path,
    eval_path: Path,
    *,
    deep_media_checks: bool = True,
) -> dict[str, Any]:
    manifest = load_manifest(storyboard_path)
    project_root = storyboard_path.parent.parent.parent
    metrics = metric_snapshot(eval_path)
    storyboard_errors = validate_storyboard(manifest)
    media = [
        validate_output(episode, media_root, metrics, project_root, deep_media_checks)
        for episode in manifest["episodes"]
    ]
    sensitive_hits = scan_sensitive(media_root)
    status = acceptance_status(media, sensitive_hits)
    if storyboard_errors:
        status = "failed"
    return {
        "schema_version": "aima-vln-final-long-acceptance/v1",
        "status": status,
        "publishable_media_ready": status == "passed",
        "storyboard": public_media_path(storyboard_path, project_root),
        "metric_source": public_media_path(eval_path, project_root),
        "metrics": metrics,
        "storyboard_errors": storyboard_errors,
        "sensitive_hits": sensitive_hits,
        "media": media,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--storyboard", type=Path, default=ROOT / "content/series/final-long-manifest.json")
    parser.add_argument("--media-root", type=Path, default=ROOT / "assets/series/final-long")
    parser.add_argument("--eval", type=Path, default=ROOT / "experiments/exp02-equivalent-v3/eval_result.json")
    parser.add_argument("--output", type=Path, default=ROOT / "content/series/final-long-acceptance.json")
    parser.add_argument("--skip-deep-media-checks", action="store_true")
    args = parser.parse_args()
    report = build_report(
        args.storyboard.resolve(),
        args.media_root.resolve(),
        args.eval.resolve(),
        deep_media_checks=not args.skip_deep_media_checks,
    )
    args.output.resolve().write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
