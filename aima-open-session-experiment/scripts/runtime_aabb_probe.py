#!/usr/bin/env python3
"""Project an authored USD obstacle layer into the navigation occupancy grid.

This probe intentionally uses the same PXR/USD path as ``IsaacBackend`` but
does not start the visual renderer or robot controller.  It is useful on
headless Isaac installations where the preinstalled visual market mesh exits
Kit before the HTTP adapter can enter its render loop.  The output is a
reproducible runtime navigation artifact, not a depth-map or empty-grid
fallback.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def _cell(value: float, resolution: float) -> int:
    return int(math.floor(value / resolution))


def project(
    usd_path: Path,
    *,
    resolution: float,
    z_min: float,
    z_max: float,
    half_length: float,
    half_width: float,
    inflation: float,
    start_xy: tuple[float, float],
) -> dict[str, Any]:
    try:
        from pxr import Usd, UsdGeom
    except ModuleNotFoundError as exc:
        if exc.name != "pxr":
            raise
        # Isaac's launcher exposes PXR only after Kit is initialized.  Keep
        # the probe self-contained so it can be executed with
        # ``/isaac-sim/python.sh`` on a clean remote shell.
        from isaacsim import SimulationApp

        app = SimulationApp({"headless": True, "disable_viewport_updates": True})
        app.update()
        try:
            from pxr import Usd, UsdGeom
        finally:
            # The caller closes the app in ``main`` through the module-level
            # hook below; keep it alive while Stage.Open is traversed.
            globals()["_probe_simulation_app"] = app

    stage = Usd.Stage.Open(str(usd_path.resolve()))
    probe_app = globals().get("_probe_simulation_app")
    if probe_app is not None:
        probe_app.update()
    raw: set[tuple[int, int]] = set()
    bounds: list[tuple[int, int]] = []
    prims = 0
    for prim in stage.Traverse():
        if not prim.IsA(UsdGeom.Cube):
            continue
        prims += 1
        size_attr = prim.GetAttribute("size")
        translate_attr = prim.GetAttribute("xformOp:translate")
        scale_attr = prim.GetAttribute("xformOp:scale")
        size = float(size_attr.Get() or 1.0)
        translate = translate_attr.Get()
        scale = scale_attr.Get()
        if translate is None or scale is None:
            continue
        half_x = abs(float(scale[0])) * size / 2.0
        half_y = abs(float(scale[1])) * size / 2.0
        half_z = abs(float(scale[2])) * size / 2.0
        lo_x, hi_x = float(translate[0]) - half_x, float(translate[0]) + half_x
        lo_y, hi_y = float(translate[1]) - half_y, float(translate[1]) + half_y
        lo_z, hi_z = float(translate[2]) - half_z, float(translate[2]) + half_z
        if hi_z < z_min or lo_z > z_max:
            continue
        min_cell = (_cell(lo_x, resolution), _cell(lo_y, resolution))
        max_cell = (_cell(hi_x, resolution), _cell(hi_y, resolution))
        for cx in range(min_cell[0], max_cell[0] + 1):
            for cy in range(min_cell[1], max_cell[1] + 1):
                raw.add((cx, cy))
        bounds.extend((min_cell, max_cell))

    start_cell = (_cell(start_xy[0], resolution), _cell(start_xy[1], resolution))
    bounds.append(start_cell)
    if not bounds:
        raise RuntimeError("USD proxy did not contain any finite obstacle bounds")
    min_x = min(cell[0] for cell in bounds) - 20
    max_x = max(cell[0] for cell in bounds) + 20
    min_y = min(cell[1] for cell in bounds) - 20
    max_y = max(cell[1] for cell in bounds) + 20
    radius = max(1, math.ceil((math.hypot(half_length, half_width) + inflation) / resolution))
    blocked: set[tuple[int, int]] = set()
    for cx, cy in raw:
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx * dx + dy * dy <= radius * radius:
                    cell = (cx + dx, cy + dy)
                    if min_x <= cell[0] <= max_x and min_y <= cell[1] <= max_y:
                        blocked.add(cell)
    blocked.discard(start_cell)
    return {
        "schema_version": "geniesim-streamvln/v1",
        "source": "usd_aabb_proxy",
        "method": "usdgeom_cube_authored_aabb",
        "usd_path": str(usd_path.resolve()),
        "cube_prims": prims,
        "raw_cells": len(raw),
        "inflated_cells": len(blocked),
        "resolution_m": resolution,
        "obstacle_z_range_m": [z_min, z_max],
        "footprint_half_extents_m": [half_length, half_width],
        "obstacle_inflation_m": inflation,
        "inflation_radius_cells": radius,
        "bounds_cells": [min_x, max_x, min_y, max_y],
        "start_cell": list(start_cell),
        "blocked_sample": [list(cell) for cell in sorted(blocked)[:32]],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--usd", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resolution", type=float, default=0.05)
    parser.add_argument("--z-min", type=float, default=0.10)
    parser.add_argument("--z-max", type=float, default=1.80)
    parser.add_argument("--half-length", type=float, default=0.34)
    parser.add_argument("--half-width", type=float, default=0.28)
    parser.add_argument("--inflation", type=float, default=0.05)
    parser.add_argument("--start-x", type=float, default=0.53)
    parser.add_argument("--start-y", type=float, default=-0.6501577213695806)
    args = parser.parse_args()
    print(json.dumps({"event": "occupancy_start", "usd": str(args.usd.resolve())}), flush=True)
    try:
        result = project(
            args.usd,
            resolution=args.resolution,
            z_min=args.z_min,
            z_max=args.z_max,
            half_length=args.half_length,
            half_width=args.half_width,
            inflation=args.inflation,
            start_xy=(args.start_x, args.start_y),
        )
    finally:
        probe_app = globals().pop("_probe_simulation_app", None)
        if probe_app is not None:
            probe_app.close()
    print(json.dumps({"event": "occupancy_proxy_direct_stage_scan", "prims": result["cube_prims"], "raw_cells": result["raw_cells"], "method": result["method"]}), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"event": "occupancy_built", "blocked": result["inflated_cells"], "output": str(args.output.resolve())}), flush=True)


if __name__ == "__main__":
    main()
