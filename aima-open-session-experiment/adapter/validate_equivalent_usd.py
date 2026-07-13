"""Open self-captured USDA/USDZ in a fresh Isaac process and report geometry."""

from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> None:
    from isaacsim import SimulationApp

    app = SimulationApp({"headless": True})
    try:
        import omni.usd
        from pxr import UsdGeom

        asset_dir = Path(os.environ["EQUIVALENT_ASSET_DIR"]).resolve()
        results = []
        for name in ("sample.usda", "sample.usdz"):
            path = asset_dir / name
            context = omni.usd.get_context()
            opened = bool(context.open_stage(str(path)))
            for _ in range(30):
                app.update()
            stage = context.get_stage()
            default_prim = stage.GetDefaultPrim() if stage else None
            points_prim = stage.GetPrimAtPath("/SelfCapturedScene/RGBDPointCloud") if stage else None
            point_count = 0
            if points_prim and points_prim.IsValid() and points_prim.IsA(UsdGeom.Points):
                point_count = len(UsdGeom.Points(points_prim).GetPointsAttr().Get() or [])
            results.append(
                {
                    "file": name,
                    "opened": opened,
                    "default_prim": str(default_prim.GetPath()) if default_prim and default_prim.IsValid() else None,
                    "point_count": point_count,
                }
            )
        ok = all(item["opened"] and item["default_prim"] == "/SelfCapturedScene" and item["point_count"] > 0 for item in results)
        print(json.dumps({"event": "equivalent_asset_validation", "ok": ok, "results": results}, ensure_ascii=False), flush=True)
        if not ok:
            raise SystemExit(1)
    finally:
        app.close()


if __name__ == "__main__":
    main()
