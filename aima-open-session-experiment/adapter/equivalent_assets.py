"""Build self-captured equivalent scene assets from audited GenieSim RGB-D frames.

The output is deliberately labelled as derived/equivalent.  It is not a
reconstruction of the course-private ``sample.*`` files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import zipfile
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image


SCHEMA_VERSION = "geniesim-self-captured-equivalent/v1"


def _inside(root: Path, value: str) -> Path:
    candidate = (root / value).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"capture path escapes root: {value}") from exc
    return candidate


def project_rgbd(
    rgb: np.ndarray,
    depth: np.ndarray,
    intrinsics: Iterable[float],
    camera_to_world: Iterable[float],
    *,
    stride: int = 4,
    min_depth_m: float = 0.10,
    max_depth_m: float = 10.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Project a pinhole RGB-D frame into world coordinates.

    Isaac/USD cameras look along camera -Z with +Y up.  Pixel coordinates use
    OpenCV's +v-down convention, hence the sign changes for camera Y and Z.
    """

    if rgb.ndim != 3 or rgb.shape[:2] != depth.shape[:2] or rgb.shape[2] < 3:
        raise ValueError("RGB and depth shapes are incompatible")
    if stride <= 0:
        raise ValueError("stride must be positive")
    k = np.asarray(list(intrinsics), dtype=np.float64).reshape(3, 3)
    transform = np.asarray(list(camera_to_world), dtype=np.float64).reshape(4, 4)
    if not np.isfinite(k).all() or not np.isfinite(transform).all() or k[0, 0] <= 0 or k[1, 1] <= 0:
        raise ValueError("calibration must be finite with positive focal lengths")
    v, u = np.mgrid[0 : depth.shape[0] : stride, 0 : depth.shape[1] : stride]
    z = depth[::stride, ::stride].astype(np.float64)
    valid = np.isfinite(z) & (z >= min_depth_m) & (z <= max_depth_m)
    z, u, v = z[valid], u[valid], v[valid]
    camera = np.stack(((u - k[0, 2]) * z / k[0, 0], -(v - k[1, 2]) * z / k[1, 1], -z, np.ones_like(z)), axis=1)
    world = (transform @ camera.T).T[:, :3]
    colors = rgb[::stride, ::stride, :3][valid].astype(np.uint8)
    return world.astype(np.float32), colors


def voxel_downsample(points: np.ndarray, colors: np.ndarray, voxel_m: float) -> tuple[np.ndarray, np.ndarray]:
    if voxel_m <= 0:
        return points, colors
    keys = np.floor(points / voxel_m).astype(np.int64)
    _, indices = np.unique(keys, axis=0, return_index=True)
    indices.sort()
    return points[indices], colors[indices]


def write_ply(path: Path, points: np.ndarray, colors: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        header = (
            "ply\nformat binary_little_endian 1.0\n"
            f"comment {SCHEMA_VERSION}\nelement vertex {len(points)}\n"
            "property float x\nproperty float y\nproperty float z\n"
            "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n"
        )
        handle.write(header.encode("ascii"))
        vertices = np.empty(len(points), dtype=[("xyz", "<f4", (3,)), ("rgb", "u1", (3,))])
        vertices["xyz"] = points
        vertices["rgb"] = colors
        handle.write(vertices.tobytes())


def write_usda_points(path: Path, points: np.ndarray, colors: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    point_rows = ",\n        ".join(f"({x:.5f}, {y:.5f}, {z:.5f})" for x, y, z in points)
    color_rows = ",\n        ".join(f"({r/255:.5f}, {g/255:.5f}, {b/255:.5f})" for r, g, b in colors)
    text = f'''#usda 1.0
(
    customLayerData = {{ string provenance = "{SCHEMA_VERSION}" }}
    defaultPrim = "SelfCapturedScene"
    metersPerUnit = 1
    upAxis = "Z"
)

def Xform "SelfCapturedScene" {{
    def Points "RGBDPointCloud" {{
        point3f[] points = [
        {point_rows}
        ]
        color3f[] primvars:displayColor = [
        {color_rows}
        ] (interpolation = "vertex")
        float[] widths = [0.025] (interpolation = "constant")
    }}
}}
'''
    path.write_text(text, encoding="utf-8")


def _iter_observations(value: Any):
    if isinstance(value, dict):
        required = {"rgb_path", "depth_path", "camera_intrinsics", "camera_to_world"}
        if required.issubset(value):
            yield value
        for child in value.values():
            yield from _iter_observations(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_observations(child)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_usdz(usda_path: Path, usdz_path: Path) -> None:
    try:
        from pxr import Sdf, UsdUtils
    except ImportError:
        # Isaac's shell does not expose pxr until Kit has started.  A USDZ is
        # an uncompressed ZIP whose payload offsets are 64-byte aligned; make
        # the single self-contained USDA package directly in that case.
        usdz_path.parent.mkdir(parents=True, exist_ok=True)
        name = usda_path.name
        base_offset = 30 + len(name.encode("utf-8"))
        padding = (-base_offset) % 64
        if 0 < padding < 4:
            padding += 64
        info = zipfile.ZipInfo(name)
        info.compress_type = zipfile.ZIP_STORED
        info.create_system = 3
        if padding:
            info.extra = struct.pack("<HH", 0xFFFF, padding - 4) + bytes(padding - 4)
        with zipfile.ZipFile(usdz_path, "w", allowZip64=False) as archive:
            archive.writestr(info, usda_path.read_bytes())
        with zipfile.ZipFile(usdz_path) as archive:
            member = archive.infolist()[0]
            data_offset = member.header_offset + 30 + len(member.filename.encode("utf-8")) + len(member.extra)
            if member.compress_type != zipfile.ZIP_STORED or data_offset % 64:
                raise RuntimeError("generated USDZ violates storage/alignment requirements")
        return
    usdz_path.parent.mkdir(parents=True, exist_ok=True)
    if not UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(str(usda_path)), str(usdz_path)):
        raise RuntimeError("UsdUtils.CreateNewUsdzPackage returned false")


def build(root: Path, json_inputs: list[Path], output_dir: Path, *, stride: int, voxel_m: float, max_points: int) -> dict[str, Any]:
    root, output_dir = root.resolve(), output_dir.resolve()
    seen: set[tuple[str, str]] = set()
    point_parts: list[np.ndarray] = []
    color_parts: list[np.ndarray] = []
    fallback_frames = 0
    for json_path in json_inputs:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        for obs in _iter_observations(payload):
            key = (str(obs["rgb_path"]), str(obs["depth_path"]))
            if key in seen:
                continue
            seen.add(key)
            if obs.get("depth_fallback"):
                fallback_frames += 1
                continue
            rgb = np.asarray(Image.open(_inside(root, key[0])).convert("RGB"))
            depth = np.load(_inside(root, key[1]), allow_pickle=False)
            points, colors = project_rgbd(rgb, depth, obs["camera_intrinsics"], obs["camera_to_world"], stride=stride)
            point_parts.append(points)
            color_parts.append(colors)
    if not point_parts:
        raise RuntimeError("no calibrated non-fallback RGB-D observations found")
    points, colors = voxel_downsample(np.concatenate(point_parts), np.concatenate(color_parts), voxel_m)
    if len(points) > max_points:
        indices = np.linspace(0, len(points) - 1, max_points, dtype=np.int64)
        points, colors = points[indices], colors[indices]
    output_dir.mkdir(parents=True, exist_ok=True)
    ply_path, usda_path, usdz_path = output_dir / "sample.ply", output_dir / "sample.usda", output_dir / "sample.usdz"
    write_ply(ply_path, points, colors)
    write_usda_points(usda_path, points, colors)
    package_usdz(usda_path, usdz_path)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "claim": "self-captured equivalent assets; not course-private originals",
        "source_json": [str(path.resolve()) for path in json_inputs],
        "unique_calibrated_frames": len(seen) - fallback_frames,
        "excluded_depth_fallback_frames": fallback_frames,
        "point_count": len(points),
        "stride": stride,
        "voxel_m": voxel_m,
        "files": {path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)} for path in (ply_path, usda_path, usdz_path)},
    }
    (output_dir / "asset-capture-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="adapter experiment root containing RGB/depth paths")
    parser.add_argument("--input-json", type=Path, nargs="+", required=True, help="sidecar/evaluation JSON files")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--stride", type=int, default=4)
    parser.add_argument("--voxel-m", type=float, default=0.03)
    parser.add_argument("--max-points", type=int, default=200_000)
    args = parser.parse_args()
    result = build(args.root, args.input_json, args.output_dir, stride=args.stride, voxel_m=args.voxel_m, max_points=args.max_points)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
