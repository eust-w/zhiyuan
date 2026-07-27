"""Independently verify the publishable navigation challenge video."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

try:
    from scripts.challenge_video_contract import (
        evidence_snapshot,
        public_repo_path,
        scan_public_bundle,
        scan_public_text,
        scan_sensitive_text,
        sha256,
        validate_claims,
    )
except ModuleNotFoundError:  # Direct ``python scripts/...`` invocation.
    from challenge_video_contract import (
        evidence_snapshot,
        public_repo_path,
        scan_public_bundle,
        scan_public_text,
        scan_sensitive_text,
        sha256,
        validate_claims,
    )


ROOT = Path(__file__).resolve().parents[1]


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def validate_storyboard(manifest: dict[str, Any], root: Path) -> list[str]:
    errors: list[str] = []
    segments = manifest.get("segments")
    if not isinstance(segments, list) or not segments:
        return ["storyboard segments must be a non-empty list"]
    total = sum(float(segment.get("duration_s", 0)) for segment in segments)
    real = sum(
        float(segment.get("duration_s", 0))
        for segment in segments
        if segment.get("source_type") == "real_recording"
    )
    if not 600 <= total <= 720:
        errors.append(f"duration outside 600-720 seconds: {total:.3f}")
    ratio = real / total if total else 0
    if ratio < 0.80:
        errors.append(f"real recording ratio below 0.80: {ratio:.4f}")
    for segment in segments:
        segment_id = segment.get("segment_id", "<missing>")
        duration = float(segment.get("duration_s", 0))
        if segment.get("source_type") != "real_recording" and duration > 4:
            errors.append(f"{segment_id}: static segment exceeds 4 seconds")
        if segment.get("source_type") == "real_recording" and duration < 2:
            errors.append(f"{segment_id}: real recording segment is shorter than 2 seconds")
        for field in ("source", "evidence_ref"):
            value = segment.get(field)
            if not isinstance(value, str) or not value:
                errors.append(f"{segment_id}: {field} is required")
                continue
            path = (root / value).resolve()
            if not _is_within(path, root):
                errors.append(f"{segment_id}: {field} escapes repository")
            elif not path.is_file():
                errors.append(f"{segment_id}: {field} does not exist")
        if segment.get("source_type") == "real_recording":
            start = float(segment.get("source_in_s", -1))
            end = float(segment.get("source_out_s", -1))
            if start < 0 or end <= start or abs((end - start) - duration) > 0.002:
                errors.append(f"{segment_id}: invalid real source window")
            if segment.get("allow_loop"):
                errors.append(f"{segment_id}: real recording must not loop")

    expected_pairs = Counter(
        (f"eval-{seed}", variant)
        for seed in range(2001, 2011)
        for variant in ("base", "lora")
    )
    actual_pairs = Counter(
        (segment.get("pair_episode_id"), segment.get("pair_variant"))
        for segment in segments
        if segment.get("pair_episode_id") is not None
    )
    if actual_pairs != expected_pairs:
        errors.append("paired evaluation must contain twenty ordered Base/LoRA replays")
    pair_order = [
        (segment.get("pair_episode_id"), segment.get("pair_variant"))
        for segment in segments
        if segment.get("pair_episode_id") is not None
    ]
    expected_order = [
        (f"eval-{seed}", variant)
        for seed in range(2001, 2011)
        for variant in ("base", "lora")
    ]
    if pair_order != expected_order:
        errors.append("paired evaluation order must be Base then LoRA for each episode")
    paired_replays = manifest.get("paired_replays")
    if not isinstance(paired_replays, list) or len(paired_replays) != 20 or len(set(paired_replays)) != 20:
        errors.append("paired_replays must list twenty distinct source files")

    expected_facts = evidence_snapshot(root)
    if manifest.get("facts") != expected_facts:
        errors.append("storyboard facts do not match authoritative evidence")
    public_hits = scan_public_bundle(manifest)
    if public_hits:
        errors.append("storyboard public text is unsafe: " + "; ".join(public_hits))
    narration = " ".join(
        str(section.get("text", ""))
        for section in manifest.get("narration_sections", [])
        if isinstance(section, dict)
    )
    errors.extend(validate_claims(narration))
    return errors


def subtitle_errors(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    blocks = [block for block in re.split(r"\n\s*\n", text.strip()) if block.strip()]
    previous_end = -1
    time_pattern = re.compile(
        r"^(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> "
        r"(\d{2}):(\d{2}):(\d{2}),(\d{3})$"
    )

    def milliseconds(values: tuple[str, ...]) -> int:
        hours, minutes, seconds, millis = map(int, values)
        return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis

    for block_index, block in enumerate(blocks, start=1):
        lines = block.splitlines()
        if len(lines) < 3:
            errors.append(f"subtitle block {block_index} is incomplete")
            continue
        if lines[0].strip() != str(block_index):
            errors.append(f"subtitle block {block_index} has wrong sequence number")
        match = time_pattern.match(lines[1].strip())
        if match is None:
            errors.append(f"subtitle block {block_index} has invalid timing")
        else:
            start = milliseconds(match.groups()[:4])
            end = milliseconds(match.groups()[4:])
            if start < previous_end or end <= start:
                errors.append(f"subtitle block {block_index} timing is not monotonic")
            previous_end = end
        copy_lines = lines[2:]
        if len(copy_lines) > 2:
            errors.append(f"subtitle block {block_index} has more than two lines")
        for line in copy_lines:
            if len(line) > 16:
                errors.append(f"subtitle block {block_index} line exceeds 16 characters")
    public_hits = scan_public_text(text)
    sensitive_hits = scan_sensitive_text(text)
    if public_hits:
        errors.append("subtitle contains forbidden public wording")
    if sensitive_hits:
        errors.append("subtitle contains sensitive content")
    return errors


def probe(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def validate_probe(info: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    streams = info.get("streams", [])
    video = next((item for item in streams if item.get("codec_type") == "video"), {})
    audio = next((item for item in streams if item.get("codec_type") == "audio"), {})
    duration = float(info.get("format", {}).get("duration", 0))
    if not 600 <= duration <= 720:
        errors.append(f"media duration outside 600-720 seconds: {duration:.3f}")
    if (
        video.get("codec_name"),
        video.get("width"),
        video.get("height"),
        video.get("r_frame_rate"),
    ) != ("h264", 1920, 1080, "30/1"):
        errors.append("video must be H.264 1920x1080 30fps")
    if (
        audio.get("codec_name"),
        audio.get("sample_rate"),
        audio.get("channels"),
    ) != ("aac", "48000", 2):
        errors.append("audio must be AAC 48kHz stereo")
    return errors


def measure_loudness(path: Path) -> dict[str, float | None]:
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-af",
            "ebur128=peak=true",
            "-f",
            "null",
            "-",
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


def validate_audio_measurement(measurement: dict[str, float | None]) -> list[str]:
    errors: list[str] = []
    integrated = measurement.get("integrated_lufs")
    peak = measurement.get("true_peak_dbfs")
    if integrated is None or not -18 <= integrated <= -14:
        errors.append(f"integrated loudness outside -18 to -14 LUFS: {integrated}")
    if peak is None or peak > -1:
        errors.append(f"true peak exceeds -1 dBTP: {peak}")
    return errors


def _stable_ffmpeg_hits(stderr: str, marker: str) -> list[str]:
    hits: list[str] = []
    for line in stderr.splitlines():
        if marker not in line:
            continue
        stable = line.strip()
        if "] " in stable:
            stable = stable.split("] ", 1)[1]
        hits.append(stable)
    return hits


def black_frame_hits(path: Path) -> list[str]:
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-vf",
            "blackdetect=d=1:pic_th=0.98",
            "-an",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return _stable_ffmpeg_hits(result.stderr, "black_duration:")


def frozen_frame_hits(path: Path) -> list[str]:
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-vf",
            "freezedetect=n=0.002:d=4",
            "-an",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return _stable_ffmpeg_hits(result.stderr, "freeze_duration:")


def decode_video(path: Path) -> tuple[bool, str]:
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0, result.stderr[-1000:]


def generate_contact_sheet(video: Path, output: Path, duration_s: float) -> dict[str, Any]:
    timestamps = list(range(0, int(duration_s), 30))
    width, height = 320, 180
    columns = 5
    rows = (len(timestamps) + columns - 1) // columns
    with tempfile.TemporaryDirectory(prefix="challenge-contact-") as directory:
        temp = Path(directory)
        frames: list[Path] = []
        for index, timestamp in enumerate(timestamps):
            frame = temp / f"{index:03d}.jpg"
            subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-ss",
                    str(timestamp),
                    "-i",
                    str(video),
                    "-frames:v",
                    "1",
                    "-vf",
                    f"scale={width}:{height}",
                    str(frame),
                ],
                check=True,
            )
            frames.append(frame)
        sheet = Image.new(
            "RGB",
            (columns * width, rows * (height + 24)),
            (8, 18, 30),
        )
        draw = ImageDraw.Draw(sheet)
        for index, (timestamp, frame) in enumerate(zip(timestamps, frames)):
            x = (index % columns) * width
            y = (index // columns) * (height + 24)
            with Image.open(frame) as image:
                sheet.paste(image.convert("RGB"), (x, y))
            draw.text((x + 8, y + height + 4), f"{timestamp // 60:02}:{timestamp % 60:02}", fill=(220, 230, 242))
        output.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(output, quality=90)
    return {
        "sample_interval_s": 30,
        "frame_count": len(timestamps),
        "sha256": sha256(output),
    }


def ocr_contact_sheet(path: Path) -> dict[str, Any]:
    if shutil.which("tesseract") is None:
        return {"status": "not_available", "languages": [], "hits": []}
    languages_result = subprocess.run(
        ["tesseract", "--list-langs"],
        capture_output=True,
        text=True,
        check=False,
    )
    languages = [
        line.strip()
        for line in languages_result.stdout.splitlines()
        if line.strip() and not line.startswith("List of")
    ]
    language = "chi_sim+eng" if "chi_sim" in languages and "eng" in languages else "eng"
    result = subprocess.run(
        ["tesseract", str(path), "stdout", "-l", language],
        capture_output=True,
        text=True,
        check=False,
    )
    text = result.stdout
    hits = [
        *(f"forbidden:{term}" for term in scan_public_text(text)),
        *(f"sensitive:{label}" for label in scan_sensitive_text(text)),
    ]
    return {
        "status": "passed" if result.returncode == 0 and not hits else "failed",
        "languages": languages,
        "language_used": language,
        "chinese_ocr_available": "chi_sim" in languages,
        "hits": hits,
    }


def acceptance_status(checks: dict[str, str]) -> str:
    return "passed" if checks and all(value == "passed" for value in checks.values()) else "failed"


def _validate_hashes(
    metadata: dict[str, Any],
    video: Path,
    srt: Path,
    voice: Path,
    project_root: Path,
) -> list[str]:
    errors: list[str] = []
    for field, path in (
        ("output_sha256", video),
        ("srt_sha256", srt),
        ("voice_sha256", voice),
    ):
        if metadata.get(field) != sha256(path):
            errors.append(f"{field} does not match generated file")
    music = metadata.get("music")
    if isinstance(music, dict):
        music_file = project_root / str(music.get("file", ""))
        provenance_file = project_root / str(music.get("provenance", ""))
        if not music_file.is_file() or music.get("sha256") != sha256(music_file):
            errors.append("BGM file or hash is invalid")
        if not provenance_file.is_file() or music.get("provenance_sha256") != sha256(provenance_file):
            errors.append("BGM provenance file or hash is invalid")
        elif "original local synthesis" not in str(music.get("license", "")):
            errors.append("BGM license is not approved")
    return errors


def build_report(
    *,
    manifest_path: Path,
    video: Path,
    srt: Path,
    media_manifest_path: Path,
    eval_path: Path,
    training_result_path: Path,
    contact_sheet: Path,
    deep_media_checks: bool,
    manual_contact_sheet_reviewed: bool,
) -> dict[str, Any]:
    project_root = manifest_path.parent.parent.parent.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    storyboard_errors = validate_storyboard(manifest, project_root)
    expected_facts = evidence_snapshot(project_root)
    media_metadata = json.loads(media_manifest_path.read_text(encoding="utf-8"))
    probe_info = probe(video)
    probe_errors = validate_probe(probe_info)
    srt_errors = subtitle_errors(srt)
    public_hits = scan_public_bundle(media_metadata)
    if scan_public_text(srt.read_text(encoding="utf-8")):
        public_hits.append("srt: forbidden public wording")
    sensitive_hits = scan_sensitive_text(srt.read_text(encoding="utf-8"))
    facts_errors: list[str] = []
    if media_metadata.get("facts") != expected_facts:
        facts_errors.append("media metadata facts do not match authoritative evidence")
    if Path(expected_facts["metric_source"]).name != eval_path.name:
        facts_errors.append("metric source argument is not eval_result.json")
    if Path(expected_facts["training_source"]).name != training_result_path.name:
        facts_errors.append("training source argument is not stage2_result_v2.json")
    pair_errors: list[str] = []
    if media_metadata.get("paired_episode_ids") != expected_facts["heldout_episode_ids"]:
        pair_errors.append("media metadata held-out IDs do not match")
    if len(media_metadata.get("paired_replays", [])) != 20:
        pair_errors.append("media metadata does not contain twenty paired replays")
    ratio = float(media_metadata.get("real_recording_ratio", 0))
    if ratio < 0.80:
        pair_errors.append("media metadata real recording ratio is below 0.80")
    hash_errors = _validate_hashes(media_metadata, video, srt, Path(media_metadata["voice"]) if Path(media_metadata["voice"]).is_absolute() else project_root / media_metadata["voice"], project_root)

    duration = float(probe_info.get("format", {}).get("duration", 0))
    contact = generate_contact_sheet(video, contact_sheet, duration)
    ocr = ocr_contact_sheet(contact_sheet)
    if ocr.get("hits"):
        sensitive_hits.extend(str(hit) for hit in ocr["hits"])

    loudness: dict[str, float | None] = {
        "integrated_lufs": None,
        "true_peak_dbfs": None,
    }
    audio_errors: list[str] = []
    black_hits: list[str] = []
    freeze_hits: list[str] = []
    decode_ok = True
    decode_error = ""
    if deep_media_checks:
        loudness = measure_loudness(video)
        audio_errors = validate_audio_measurement(loudness)
        black_hits = black_frame_hits(video)
        freeze_hits = frozen_frame_hits(video)
        decode_ok, decode_error = decode_video(video)

    checks = {
        "storyboard": "passed" if not storyboard_errors else "failed",
        "media": "passed" if not probe_errors else "failed",
        "text": "passed" if not public_hits and not sensitive_hits and not srt_errors else "failed",
        "audio": "passed" if not audio_errors else "failed",
        "pairing": "passed" if not pair_errors else "failed",
        "metrics": "passed" if not facts_errors else "failed",
        "hashes": "passed" if not hash_errors else "failed",
        "decode": "passed" if decode_ok else "failed",
        "black_frames": "passed" if not black_hits else "failed",
        "contact_sheet_review": "passed" if manual_contact_sheet_reviewed else "failed",
    }
    status = acceptance_status(checks)
    return {
        "schema_version": "geniesim-streamvln-challenge-acceptance/v1",
        "status": status,
        "publishable_media_ready": status == "passed",
        "checks": checks,
        "storyboard": public_repo_path(manifest_path, project_root),
        "video": public_repo_path(video, project_root),
        "srt": public_repo_path(srt, project_root),
        "media_manifest": public_repo_path(media_manifest_path, project_root),
        "metric_source": public_repo_path(eval_path, project_root),
        "training_source": public_repo_path(training_result_path, project_root),
        "contact_sheet": public_repo_path(contact_sheet, project_root),
        "duration_s": duration,
        "real_recording_ratio": ratio,
        "facts": expected_facts,
        "storyboard_errors": storyboard_errors,
        "probe_errors": probe_errors,
        "subtitle_errors": srt_errors,
        "public_hits": public_hits,
        "sensitive_hits": sensitive_hits,
        "metric_errors": facts_errors,
        "pairing_errors": pair_errors,
        "hash_errors": hash_errors,
        "loudness": loudness,
        "audio_errors": audio_errors,
        "black_frame_hits": black_hits,
        "freeze_hits": freeze_hits,
        "freeze_review": {
            "status": "informational",
            "detected_intervals": len(freeze_hits),
            "policy": (
                "Non-real storyboard segments longer than four seconds fail validation. "
                "Freezes detected inside continuous real recordings are retained for "
                "manual review and are not treated as static-card violations."
            ),
        },
        "decode_error": decode_error,
        "contact_sheet_sampling": contact,
        "ocr": ocr,
        "manual_contact_sheet_reviewed": manual_contact_sheet_reviewed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "content/challenge-video/challenge-manifest.json",
    )
    parser.add_argument(
        "--video",
        type=Path,
        default=ROOT / "assets/challenge-video/final/geniesim-streamvln-challenge.mp4",
    )
    parser.add_argument(
        "--srt",
        type=Path,
        default=ROOT / "assets/challenge-video/final/geniesim-streamvln-challenge.srt",
    )
    parser.add_argument(
        "--media-manifest",
        type=Path,
        default=ROOT / "assets/challenge-video/final/geniesim-streamvln-challenge-media-manifest.json",
    )
    parser.add_argument(
        "--eval",
        type=Path,
        default=ROOT / "experiments/exp02-equivalent-v3/eval_result.json",
    )
    parser.add_argument(
        "--training-result",
        type=Path,
        default=ROOT / "experiments/exp02-equivalent-v3/stage2_result_v2.json",
    )
    parser.add_argument(
        "--contact-sheet",
        type=Path,
        default=ROOT / "assets/challenge-video/preview/contact-sheet.jpg",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "content/challenge-video/acceptance.json",
    )
    parser.add_argument("--skip-deep-media-checks", action="store_true")
    parser.add_argument("--manual-contact-sheet-reviewed", action="store_true")
    parser.add_argument("--public-text-only", action="store_true")
    parser.add_argument("--publish-package", type=Path)
    args = parser.parse_args()

    if args.public_text_only:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        hits = scan_public_bundle(manifest)
        if args.publish_package:
            hits.extend(
                scan_public_bundle(
                    json.loads(args.publish_package.read_text(encoding="utf-8"))
                )
            )
        print(json.dumps({"status": "passed" if not hits else "failed", "hits": hits}, ensure_ascii=False, indent=2))
        raise SystemExit(0 if not hits else 1)

    report = build_report(
        manifest_path=args.manifest.resolve(),
        video=args.video.resolve(),
        srt=args.srt.resolve(),
        media_manifest_path=args.media_manifest.resolve(),
        eval_path=args.eval.resolve(),
        training_result_path=args.training_result.resolve(),
        contact_sheet=args.contact_sheet.resolve(),
        deep_media_checks=not args.skip_deep_media_checks,
        manual_contact_sheet_reviewed=args.manual_contact_sheet_reviewed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "checks": report["checks"],
                "duration_s": report["duration_s"],
                "real_recording_ratio": report["real_recording_ratio"],
                "loudness": report["loudness"],
                "black_frame_hits": len(report["black_frame_hits"]),
                "freeze_hits": len(report["freeze_hits"]),
                "ocr": report["ocr"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
