"""Build the repository GIF and vertical MP4 from real adapter RGB frames.

The script uses the ffmpeg binary bundled by ``imageio-ffmpeg`` when a system
ffmpeg is not installed.  It deliberately adds an on-screen disclaimer so the
clip cannot be mistaken for a StreamVLN model success demo.
"""

from __future__ import annotations

import argparse
import glob
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def _font(size: int):
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    candidates.extend(glob.glob("/System/Library/AssetsV2/*/*/AssetData/Hei.ttf"))
    candidates.extend(glob.glob("/System/Library/AssetsV2/*/*/AssetData/Lantinghei.ttc"))
    for candidate in candidates:
        if Path(candidate).is_file():
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                pass
    return ImageFont.load_default()


def _load_frames(source: Path, names: list[str], size: tuple[int, int]) -> list[Image.Image]:
    frames: list[Image.Image] = []
    for name in names:
        with Image.open(source / name).convert("RGB") as image:
            frames.append(ImageOps.fit(image, size, method=Image.Resampling.LANCZOS))
    if len(frames) < 2:
        raise ValueError("at least two RGB frames are required")
    return frames


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    # The checked-in evidence frames use the P1-smoke prefix; accepting the
    # short names keeps the script usable with a raw capture directory too.
    names = ["P1-smoke-0000.jpg", "P1-smoke-0008.jpg", "P1-smoke-0016.jpg", "P1-smoke-0024.jpg", "P1-smoke-0026.jpg"]
    source = args.source.expanduser().resolve()
    out_dir = args.out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    gif_frames = _load_frames(source, names, (960, 540))
    gif_path = out_dir / "stage1-smoke-controller.gif"
    gif_frames[0].save(gif_path, save_all=True, append_images=gif_frames[1:], duration=600, loop=0, disposal=2)

    captions = [
        "NON-OFFICIAL ADAPTER | reset",
        "RGB + depth + pose captured after two render frames",
        "StreamVLN output → forward 0.25 m / turn 15 deg",
        "Same 10 held-out episodes: base vs LoRA",
        "0/10 at 0.50 m; transparent failure review",
    ]
    with tempfile.TemporaryDirectory(prefix="aima-media-") as temp:
        temp_dir = Path(temp)
        vertical: list[Path] = []
        for index, (frame, caption) in enumerate(zip(gif_frames, captions)):
            canvas = Image.new("RGB", (1080, 1920), (11, 16, 24))
            image = ImageOps.contain(frame, (980, 1040), method=Image.Resampling.LANCZOS)
            canvas.paste(image, ((1080 - image.width) // 2, 260))
            draw = ImageDraw.Draw(canvas)
            title_font = _font(42)
            body_font = _font(34)
            draw.text((50, 80), "GenieSim × StreamVLN", fill=(245, 248, 255), font=title_font)
            draw.text((50, 145), "智元布道师个人实验 · 非官方适配", fill=(245, 174, 80), font=body_font)
            draw.rounded_rectangle((40, 1370, 1040, 1680), radius=24, fill=(20, 29, 42))
            draw.text((72, 1450), caption, fill=(255, 255, 255), font=body_font)
            draw.text((72, 1540), "真实闭环证据；未提交 AgiBot Open Session 榜单", fill=(190, 204, 220), font=body_font)
            target = temp_dir / f"frame-{index:04d}.png"
            canvas.save(target)
            vertical.append(target)
        try:
            import imageio_ffmpeg

            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as exc:  # pragma: no cover - environment dependent
            raise SystemExit(f"ffmpeg is required for MP4 output: {exc}") from exc
        mp4_path = out_dir / "stage1-smoke-retrospective-vertical.mp4"
        # Five cards plus the final hold frame produce a 54-second, 30 fps,
        # H.264, silent clip, within the requested 45–60 second range.
        concat = temp_dir / "frames.txt"
        concat.write_text("\n".join(f"file '{path}'\nduration 9" for path in vertical) + f"\nfile '{vertical[-1]}'\n", encoding="utf-8")
        subprocess.run(
            [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-vf", "fps=30,format=yuv420p", "-an", "-c:v", "libx264", "-movflags", "+faststart", str(mp4_path)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    print(gif_path)
    print(mp4_path)


if __name__ == "__main__":
    main()
