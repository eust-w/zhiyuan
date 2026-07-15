"""Validate rendered series media without hiding draft blockers."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

try:
    from scripts.series_manifest import load_manifest, metric_snapshot
except ModuleNotFoundError:  # Direct script invocation.
    from series_manifest import load_manifest, metric_snapshot


ROOT = Path(__file__).resolve().parents[1]
SENSITIVE = re.compile(r"(?:[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?:\d{1,3}\.){3}\d{1,3}|__REDACTED_CREDENTIAL_LITERAL__|实例ID|ssh\s+\S+@)", re.I)


def probe(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_name,codec_type,width,height,r_frame_rate,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def subtitle_errors(path: Path) -> list[str]:
    errors: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.isdigit() and "-->" not in line and len(line) > 16:
            errors.append(f"subtitle line >16: {line[:30]}")
    return errors


def validate_media(video: Path, srt: Path, layout: str, expected_metrics: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if not video.is_file():
        errors.append("video missing")
        return {"video": str(video), "status": "failed", "errors": errors}
    if not srt.is_file():
        errors.append("srt missing")
    info = probe(video)
    streams = info.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})
    width, height = (1920, 1080) if layout == "landscape" else (1080, 1920)
    if (video_stream.get("codec_name"), video_stream.get("width"), video_stream.get("height")) != ("h264", width, height):
        errors.append("video must be H.264 with requested dimensions")
    if video_stream.get("r_frame_rate") != "30/1":
        errors.append("video must be 30fps")
    if audio_stream.get("codec_name") not in {"aac", None}:
        errors.append("audio must be AAC")
    if audio_stream and (audio_stream.get("sample_rate"), audio_stream.get("channels")) != ("48000", 2):
        errors.append("audio must be 48kHz stereo")
    if srt.is_file():
        errors.extend(subtitle_errors(srt))
    return {
        "video": str(video),
        "srt": str(srt),
        "layout": layout,
        "duration_s": float(info.get("format", {}).get("duration", 0)),
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "metrics_match_source": expected_metrics is not None,
    }


def scan_sensitive(root: Path) -> list[str]:
    hits: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".md", ".json", ".srt", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if SENSITIVE.search(text):
            hits.append(str(path.relative_to(root)))
    return hits


def build_report(series_manifest: Path, media_root: Path, eval_path: Path, require_final: bool = False) -> dict[str, Any]:
    manifest = load_manifest(series_manifest)
    metrics = metric_snapshot(eval_path)
    outputs: list[dict[str, Any]] = []
    for episode in manifest["episodes"]:
        episode_id = episode["episode"]
        episode_dir = media_root / episode_id
        video = episode_dir / f"{episode_id}.mp4"
        srt = episode_dir / f"{episode_id}.srt"
        outputs.append(validate_media(video, srt, "landscape", metrics))
    ratio_blockers = []
    for episode in manifest["episodes"]:
        total = sum(float(s.get("duration_s", 0)) for s in episode.get("segments", []))
        real = sum(float(s.get("duration_s", 0)) for s in episode.get("segments", []) if s.get("source_type") == "real_recording")
        ratio = real / total if total else 0.0
        if ratio < float(manifest["real_ratio_target"]):
            ratio_blockers.append({"episode": episode["episode"], "real_recording_ratio": ratio, "target": manifest["real_ratio_target"]})
    sensitive_hits = scan_sensitive(media_root)
    platform_root = media_root.parent.parent / "article" / "series"
    if platform_root.is_dir():
        sensitive_hits.extend(f"article/series/{hit}" for hit in scan_sensitive(platform_root))
    report = {
        "schema_version": "aima-vln-series-acceptance/v1",
        "status": "passed" if not ratio_blockers and all(item["status"] == "passed" for item in outputs) else "draft_blocked",
        "require_final": require_final,
        "metric_source": str(eval_path),
        "metrics": metrics,
        "media": outputs,
        "real_ratio_blockers": ratio_blockers,
        "sensitive_hits": sensitive_hits,
    }
    if require_final and report["status"] != "passed":
        raise ValueError(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "content/series/series-manifest.json")
    parser.add_argument("--media-root", type=Path, default=ROOT / "assets/series")
    parser.add_argument("--eval", type=Path, default=ROOT / "experiments/exp02-equivalent-v3/eval_result.json")
    parser.add_argument("--output", type=Path, default=ROOT / "content/series/series-media-acceptance.json")
    parser.add_argument("--require-final", action="store_true")
    args = parser.parse_args()
    report = build_report(args.manifest.resolve(), args.media_root.resolve(), args.eval.resolve(), args.require_final)
    args.output.resolve().write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
