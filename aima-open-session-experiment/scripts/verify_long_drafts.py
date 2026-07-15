"""Verify the duration/codec envelope of the explicitly watermarked rough cuts."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def probe(path: Path) -> dict[str, object]:
    return json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=codec_name,codec_type,width,height,r_frame_rate,sample_rate,channels",
        "-of", "json", str(path),
    ], text=True))


def check_srt(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line and not line.isdigit() and "-->" not in line and len(line) > 16]


def build_report(root: Path = ROOT) -> dict[str, object]:
    outputs: list[dict[str, object]] = []
    for stage in ("stage0", "stage1", "stage2", "stage3"):
        directory = root / "assets/series/long-drafts" / stage
        video = directory / f"{stage}-rough-cut-draft.mp4"
        srt = directory / f"{stage}-rough-cut-draft.srt"
        manifest = directory / f"{stage}-rough-cut-manifest.json"
        errors: list[str] = []
        if not video.is_file():
            errors.append("video missing")
            outputs.append({"episode": stage, "status": "failed", "errors": errors})
            continue
        info = probe(video)
        streams = info.get("streams", [])
        v = next((x for x in streams if x.get("codec_type") == "video"), {})
        a = next((x for x in streams if x.get("codec_type") == "audio"), {})
        duration = float(info.get("format", {}).get("duration", 0))
        if (v.get("codec_name"), v.get("width"), v.get("height"), v.get("r_frame_rate")) != ("h264", 1920, 1080, "30/1"):
            errors.append("rough cut must be H.264 1920x1080 30fps")
        if (a.get("codec_name"), a.get("sample_rate"), a.get("channels")) != ("aac", "48000", 2):
            errors.append("rough cut must be AAC 48kHz stereo")
        if not 600 <= duration <= 900:
            errors.append(f"duration outside 10-15 minute envelope: {duration:.2f}s")
        if not srt.is_file():
            errors.append("rough-cut SRT missing")
        elif check_srt(srt):
            errors.append("rough-cut SRT line exceeds 16 characters")
        if not manifest.is_file():
            errors.append("rough-cut manifest missing")
        else:
            metadata = json.loads(manifest.read_text(encoding="utf-8"))
            if metadata.get("status") != "rough_cut_draft" or metadata.get("source_reuse") is not True or metadata.get("real_recording_ratio_verified") is not False:
                errors.append("rough-cut disclosure metadata missing")
        outputs.append({"episode": stage, "duration_s": duration, "status": "passed" if not errors else "failed", "errors": errors})
    return {
        "schema_version": "aima-vln-long-draft-acceptance/v1",
        "status": "passed_rough_cut_only" if all(item["status"] == "passed" for item in outputs) else "failed",
        "final_publishable": False,
        "reason": "所有长片均为旧素材循环粗剪，等待 GPUFree 新录屏后重渲染",
        "media": outputs,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "content/series/long-draft-acceptance.json")
    args = parser.parse_args()
    report = build_report(ROOT)
    args.output.resolve().write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "passed_rough_cut_only":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
