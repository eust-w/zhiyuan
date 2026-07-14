#!/usr/bin/env python3
"""Build a stable, standard-Cube USD AABB proxy for the equivalent scene.

The captured point cloud remains the visual equivalent asset.  This proxy is
intentionally a separate navigation layer: it contains only valid USD Cube
prims, so Isaac's BBoxCache does not need to touch the malformed mesh prims in
the captured point cloud.  It is not presented as the private course asset.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


BOXES = [
    # perimeter of the market aisle; leave a generous open centre around the
    # verified G2 start pose (0.53, -0.65).
    (-4.50, 0.00, 0.20, 9.40, 1.70, "perimeter_west"),
    (4.50, 0.00, 0.20, 9.40, 1.70, "perimeter_east"),
    (0.00, -4.70, 9.00, 0.20, 1.70, "perimeter_south"),
    (0.00, 4.70, 9.00, 0.20, 1.70, "perimeter_north"),
    # shelf blocks.  Each gap is wider than the inflated G2 footprint and is
    # reachable by the 24-heading A* planner.
    (-2.35, 1.65, 0.55, 4.60, 1.70, "shelf_left"),
    (2.35, 1.65, 0.55, 4.60, 1.70, "shelf_right"),
    (-1.10, -3.05, 1.80, 0.55, 1.70, "shelf_south_left"),
    (1.10, -3.05, 1.80, 0.55, 1.70, "shelf_south_right"),
    (-1.10, 3.05, 1.80, 0.55, 1.70, "shelf_north_left"),
    (1.10, 3.05, 1.80, 0.55, 1.70, "shelf_north_right"),
]


def _box_usda(index: int, box: tuple[float, float, float, float, float, str]) -> str:
    x, y, sx, sy, sz, label = box
    return f'''    def Xform "ObstacleRun_{index:04d}_{label}" {{
        def Cube "obstacle" {{
            double size = 1
            float3 xformOp:scale = ({sx:.4f}, {sy:.4f}, {sz:.4f})
            double3 xformOp:translate = ({x:.4f}, {y:.4f}, {sz / 2.0:.4f})
            uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
        }}
    }}
'''


def build(output: Path) -> dict[str, object]:
    output.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(_box_usda(i, box) for i, box in enumerate(BOXES))
    text = f'''#usda 1.0
(
    defaultPrim = "AABBProxy"
    metersPerUnit = 1
    upAxis = "Z"
)

def Xform "AABBProxy" {{
{body}}}
'''
    output.write_text(text, encoding="utf-8")
    return {
        "schema_version": "geniesim-streamvln/equivalent-aabb-proxy/v1",
        "asset_role": "runtime_navigation_obstacle_layer",
        "source_visual_asset": "artifacts/equivalent-scene/sample.ply",
        "course_private_asset": False,
        "bbox_prim_type": "UsdGeom.Cube",
        "resolution_m": 0.05,
        "obstacle_height_m": [0.10, 1.80],
        "box_count": len(BOXES),
        "boxes": [
            {"x": x, "y": y, "size_x": sx, "size_y": sy, "size_z": sz, "label": label}
            for x, y, sx, sy, sz, label in BOXES
        ],
        "output": str(output),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    manifest = build(args.output)
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
