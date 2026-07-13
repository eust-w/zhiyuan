"""Isaac Sim bridge for the non-official GenieSim x StreamVLN adapter.

This module deliberately keeps Isaac imports inside runtime methods.  The
protocol, dataset and test suite can therefore run on a normal workstation,
while the GPUFree entrypoint owns the Isaac main thread and only exposes a
small loopback HTTP service to worker threads.
"""

from __future__ import annotations

import json
import math
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .occupancy import OccupancyGrid, astar, footprint_cells
from .protocol import EpisodeReset, EpisodeStep, build_observation


YAW_BINS = 24
FORWARD_STEP_M = 0.25
TURN_RAD = 2.0 * math.pi / YAW_BINS


def quat_wxyz_from_yaw(yaw: float) -> tuple[float, float, float, float]:
    """Return the wxyz quaternion used by GenieSim's base pose API."""

    return (math.cos(yaw / 2.0), 0.0, 0.0, math.sin(yaw / 2.0))


def pose_matrix_xy_yaw(x: float, y: float, yaw: float) -> list[float]:
    c, s = math.cos(yaw), math.sin(yaw)
    return [c, -s, 0.0, x, s, c, 0.0, y, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]


def action_pose(state: tuple[float, float, int], action_id: int) -> tuple[float, float, int] | None:
    """Apply one public action to a continuous XY / discrete-yaw state."""

    x, y, yaw_bin = state
    yaw_bin %= YAW_BINS
    if action_id == 0:
        return None
    if action_id == 2:
        return x, y, (yaw_bin + 1) % YAW_BINS
    if action_id == 3:
        return x, y, (yaw_bin - 1) % YAW_BINS
    if action_id == 1:
        yaw = yaw_bin * TURN_RAD
        return x + FORWARD_STEP_M * math.cos(yaw), y + FORWARD_STEP_M * math.sin(yaw), yaw_bin
    raise ValueError(f"unsupported action_id: {action_id}")


@dataclass
class _PendingCapture:
    event: threading.Event
    base: dict[str, Any]
    frames_left: int = 2
    result: dict[str, Any] | None = None
    error: BaseException | None = None


class IsaacBackend:
    """Main-thread Isaac implementation behind :class:`AdapterService`."""

    def __init__(self, root: Path, api_core: Any, world: Any, adapter_config: dict[str, Any]):
        self.root = root.expanduser().resolve()
        self.api_core = api_core
        self.world = world
        self.config = adapter_config
        self.root.mkdir(parents=True, exist_ok=True)
        self.media_root = self.root / "runtime" / "observations"
        self.media_root.mkdir(parents=True, exist_ok=True)
        (self.root / "runtime").mkdir(parents=True, exist_ok=True)

        nav = adapter_config.get("navigation", {})
        self.project_usd_aabbs = bool(nav.get("project_usd_aabbs", True))
        self.resolution = float(nav.get("resolution_m", 0.05))
        self.forward_step = float(nav.get("forward_step_m", FORWARD_STEP_M))
        self.success_radius = float(nav.get("success_radius_m", 0.5))
        self.max_steps = int(nav.get("max_steps", 200))
        self.half_length = float(nav.get("footprint_half_length_m", 0.34))
        self.half_width = float(nav.get("footprint_half_width_m", 0.28))
        self.inflation = float(nav.get("inflation_m", 0.05))
        camera_cfg = adapter_config.get("camera", {})
        self.camera_path = str(camera_cfg.get("prim_path", "/genie/head_link3/head_front_Camera"))
        self.width = int(camera_cfg.get("width", 640))
        self.height = int(camera_cfg.get("height", 400))

        self.grid: OccupancyGrid | None = None
        self.start_pose = (0.0, 0.0, 0)
        self.current_pose = self.start_pose
        self.goal_cell: tuple[int, int] | None = None
        self.goal_world = (0.0, 0.0)
        self.bootstrapped = False
        self.episode_id: str | None = None
        self.instruction = ""
        self.target_id = "red-target-marker"
        self.step_id = 0
        self.collisions = 0
        self.terminated = False
        self.truncated = False

        self._rgb_annotator: Any = None
        self._depth_annotator: Any = None
        self._robot_prim: Any = None
        self._main_tasks: queue.Queue[tuple[Any, tuple[Any, ...], threading.Event, dict[str, Any]]] = queue.Queue()
        self._main_thread_id: int | None = None
        self._pending: _PendingCapture | None = None
        self._op_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Main-thread bootstrap and scene inspection
    # ------------------------------------------------------------------
    def bootstrap_main_thread(self) -> None:
        """Load G2 + market scene and prepare sensors; call only on Isaac's thread."""

        if self.bootstrapped:
            return
        scene = self.config.get("scene", {})
        robot = self.config.get("robot", {})
        init_position = list(scene.get("initial_position", [0.53, -0.6501577213695806, 0.0]))
        init_rotation = list(scene.get("initial_rotation_wxyz", [1.0, 0.0, 0.0, 0.0]))
        scene_usd = str(scene.get("scene_usd", "background/market/market_2/background.usda"))
        scene_usd = scene_usd.replace("source/geniesim/assets/", "")
        robot_cfg = str(robot.get("config", "G2_omnipicker.json"))
        print(json.dumps({"event": "init_robot_cfg", "robot": robot_cfg, "scene": scene_usd}), flush=True)

        self._main_thread_id = threading.get_ident()
        self._load_usd_scene(robot_cfg, scene_usd, init_position, init_rotation)
        print(json.dumps({"event": "init_robot_cfg_done"}), flush=True)
        self.start_pose = (float(init_position[0]), float(init_position[1]), 0)
        self.current_pose = self.start_pose

        self._attach_sensors()
        print(json.dumps({"event": "sensors_attached"}), flush=True)
        self.grid = self._build_occupancy_grid()
        print(json.dumps({"event": "occupancy_built", "blocked": len(self.grid.blocked)}), flush=True)
        self.goal_cell = self._choose_goal_cell()
        print(json.dumps({"event": "goal_selected", "goal": self.goal_cell}), flush=True)
        if self.goal_cell is None:
            raise RuntimeError("no reachable target cell found in market_00_g2")
        self.goal_world = self.grid.cell_to_world(self.goal_cell)
        self._add_red_marker(self.goal_world)
        print(json.dumps({"event": "marker_added"}), flush=True)
        (self.root / "runtime" / "occupancy.json").write_text(
            json.dumps(
                {
                    "resolution_m": self.grid.resolution,
                    "bounds": self.grid.bounds,
                    "blocked_cells": len(self.grid.blocked),
                    "start_cell": self.grid.world_to_cell(*self.start_pose[:2]),
                    "goal_cell": self.goal_cell,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        self.bootstrapped = True

    def _attach_sensors(self) -> None:
        import omni.replicator.core as rep

        render_product = rep.create.render_product(self.camera_path, (self.width, self.height))
        self._depth_annotator = rep.AnnotatorRegistry.get_annotator("distance_to_image_plane")
        self._depth_annotator.attach(render_product)
        self._rgb_annotator = rep.AnnotatorRegistry.get_annotator("rgb")
        self._rgb_annotator.attach(render_product)

    def _load_usd_scene(
        self,
        robot_cfg_name: str,
        scene_usd: str,
        init_position: list[float],
        init_rotation: list[float],
    ) -> None:
        """Load only the public GenieSim USD assets, avoiding its ROS/control stack."""

        from geniesim.app.utils import RobotCfg
        from geniesim.utils import system_utils
        from isaacsim.core.prims import SingleXFormPrim
        from isaacsim.core.utils.stage import add_reference_to_stage

        robot_cfg = RobotCfg(str(system_utils.app_root_path()) + "/robot_cfg/" + robot_cfg_name)
        robot_usd = str(system_utils.assets_path()) + "/" + robot_cfg.robot_usd
        scene_path = str(system_utils.assets_path()) + "/" + scene_usd
        add_reference_to_stage(robot_usd, robot_cfg.robot_prim_path)
        add_reference_to_stage(scene_path, "/World")
        self._robot_prim = SingleXFormPrim(
            prim_path=robot_cfg.robot_prim_path,
            position=init_position,
            orientation=init_rotation,
        )
        self.world.play()

    def _build_occupancy_grid(self) -> OccupancyGrid:
        from pxr import Usd, UsdGeom
        import omni.usd

        stage = omni.usd.get_context().get_stage()
        if not self.project_usd_aabbs:
            start_cell = self._world_to_cell(self.start_pose[0], self.start_pose[1])
            margin = max(80, round(10.0 / self.resolution))
            return OccupancyGrid(
                resolution=self.resolution,
                blocked=set(),
                bounds=(
                    start_cell[0] - margin,
                    start_cell[0] + margin,
                    start_cell[1] - margin,
                    start_cell[1] + margin,
                ),
                forward_step_m=self.forward_step,
            )
        bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])
        print(json.dumps({"event": "occupancy_start"}), flush=True)
        raw_cells: set[tuple[int, int]] = set()
        all_cells: list[tuple[int, int]] = []
        z_min = float(self.config.get("navigation", {}).get("obstacle_z_min_m", 0.10))
        z_max = float(self.config.get("navigation", {}).get("obstacle_z_max_m", 1.80))

        for index, prim in enumerate(stage.Traverse()):
            if index and index % 1000 == 0:
                print(json.dumps({"event": "occupancy_progress", "prims": index}), flush=True)
            path = str(prim.GetPath())
            # The G2 visual USD contains several malformed face-varying mesh
            # primvars.  Computing a bbox for every leaf can make Hydra abort
            # before Python can catch an exception, so use stable top-level
            # background Xforms as obstacle proxies and keep the exact policy
            # documented in the runtime manifest.
            if not path.startswith("/World/Background/") or not prim.IsA(UsdGeom.Xform):
                continue
            if path.count("/") > 4:
                continue
            try:
                box = bbox_cache.ComputeWorldBound(prim).ComputeAlignedBox()
                lo, hi = box.GetMin(), box.GetMax()
                if not all(math.isfinite(float(v)) for v in (*lo, *hi)):
                    continue
                if float(hi[2]) < z_min or float(lo[2]) > z_max:
                    continue
                if float(hi[0] - lo[0]) > 100 or float(hi[1] - lo[1]) > 100:
                    continue
                min_cell = self._world_to_cell(float(lo[0]), float(lo[1]))
                max_cell = self._world_to_cell(float(hi[0]), float(hi[1]))
                for cx in range(min_cell[0], max_cell[0] + 1):
                    for cy in range(min_cell[1], max_cell[1] + 1):
                        raw_cells.add((cx, cy))
                all_cells.extend((min_cell, max_cell))
            except Exception:
                continue

        start_cell = self._world_to_cell(self.start_pose[0], self.start_pose[1])
        all_cells.append((start_cell, start_cell))
        if not all_cells:
            raise RuntimeError("USD scene did not yield any finite obstacle bounds")
        min_x = min(c[0] for pair in all_cells for c in pair) - 20
        max_x = max(c[0] for pair in all_cells for c in pair) + 20
        min_y = min(c[1] for pair in all_cells for c in pair) - 20
        max_y = max(c[1] for pair in all_cells for c in pair) + 20

        # Expand AABB cells by the robot footprint plus the required 5 cm
        # safety inflation. This is conservative and deterministic.
        radius = max(1, math.ceil((math.hypot(self.half_length, self.half_width) + self.inflation) / self.resolution))
        blocked: set[tuple[int, int]] = set()
        for cx, cy in raw_cells:
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    if dx * dx + dy * dy <= radius * radius:
                        cell = (cx + dx, cy + dy)
                        if min_x <= cell[0] <= max_x and min_y <= cell[1] <= max_y:
                            blocked.add(cell)
        blocked.discard(start_cell)
        return OccupancyGrid(
            resolution=self.resolution,
            blocked=blocked,
            bounds=(min_x, max_x, min_y, max_y),
            forward_step_m=self.forward_step,
        )

    def _choose_goal_cell(self) -> tuple[int, int] | None:
        assert self.grid is not None
        start_cell = self.grid.world_to_cell(*self.start_pose[:2])
        candidates: list[tuple[float, tuple[int, int]]] = []
        for x in range(self.grid.bounds[0], self.grid.bounds[1] + 1):  # type: ignore[index]
            for y in range(self.grid.bounds[2], self.grid.bounds[3] + 1):  # type: ignore[index]
                cell = (x, y)
                if not self.grid.is_free(cell):
                    continue
                distance = math.dist(self.grid.cell_to_world(start_cell), self.grid.cell_to_world(cell))
                if 2.0 <= distance <= 6.0:
                    candidates.append((abs(distance - 4.0), cell))
        for _, cell in sorted(candidates):
            if astar(self.grid, (start_cell[0], start_cell[1], 0), (cell[0], cell[1], 0)):
                return cell
        return None

    def _add_red_marker(self, position: tuple[float, float]) -> None:
        from pxr import Gf, Sdf, UsdGeom, UsdShade
        import omni.usd

        stage = omni.usd.get_context().get_stage()
        UsdGeom.Xform.Define(stage, "/World/RedTargetMarker")
        marker = UsdGeom.Cube.Define(stage, "/World/RedTargetMarker/plate")
        marker.CreateSizeAttr(1.0)
        marker.AddTranslateOp().Set(Gf.Vec3d(position[0], position[1], 1.0))
        marker.AddScaleOp().Set(Gf.Vec3f(0.12, 0.12, 0.12))
        material = UsdShade.Material.Define(stage, Sdf.Path("/World/RedTargetMarker/RedMaterial"))
        shader = UsdShade.Shader.Define(stage, Sdf.Path("/World/RedTargetMarker/RedMaterial/PreviewSurface"))
        shader.CreateIdAttr("UsdPreviewSurface")
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(1.0, 0.0, 0.0))
        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.45)
        material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
        UsdShade.MaterialBindingAPI(marker.GetPrim()).Bind(material)

    # ------------------------------------------------------------------
    # AdapterService backend methods (HTTP threads block on render queue)
    # ------------------------------------------------------------------
    def health(self) -> dict[str, Any]:
        return {
            "ready": self.bootstrapped,
            "scene": self.config.get("scene", {}).get("name", "market_00_g2"),
            "robot": self.config.get("robot", {}).get("name", "G2_omnipicker"),
            "camera": self.camera_path,
            "occupancy_grid": self.grid is not None,
            "occupancy_source": "usd_aabb" if self.project_usd_aabbs else "runtime_safe_fallback_no_usd_aabb",
            "write_root": str(self.root),
        }

    def reset(self, request: EpisodeReset) -> dict[str, Any]:
        with self._op_lock:
            if not self.bootstrapped or self.grid is None or self.goal_cell is None:
                raise RuntimeError("Isaac backend is not bootstrapped")
            self.episode_id = request.episode_id
            self.instruction = request.instruction
            self.target_id = request.target_id
            self.current_pose = self.start_pose
            self.step_id = 0
            self.collisions = 0
            self.terminated = False
            self.truncated = False
            self._call_main(self._set_pose_on_main, self.current_pose)
            return self._wait_for_capture({"collision": False, "blocked": False, "terminated": False, "truncated": False})

    def step(self, request: EpisodeStep) -> dict[str, Any]:
        with self._op_lock:
            if self.episode_id is None:
                raise RuntimeError("episode is not reset")
            if self.terminated or self.truncated:
                return self._wait_for_capture(
                    {"collision": False, "blocked": False, "terminated": self.terminated, "truncated": self.truncated}
                )
            blocked = False
            collision = False
            proposed = action_pose(self.current_pose, request.action_id)
            if proposed is None:
                self.terminated = True
            elif request.action_id == 1:
                if self._pose_is_free(proposed):
                    self.current_pose = proposed
                    self._call_main(self._set_pose_on_main, self.current_pose)
                else:
                    blocked = True
                    collision = True
                    self.collisions += 1
            else:
                self.current_pose = proposed
                self._call_main(self._set_pose_on_main, self.current_pose)
            self.step_id += 1
            self.truncated = self.step_id >= self.max_steps and not self.terminated
            return self._wait_for_capture(
                {"collision": collision, "blocked": blocked, "terminated": self.terminated, "truncated": self.truncated}
            )

    def close(self, episode_id: str) -> dict[str, Any]:
        return {
            "schema_version": "geniesim-streamvln/v1",
            "episode_id": episode_id,
            "closed": True,
            "steps": self.step_id,
            "collisions": self.collisions,
        }

    def on_frame(self) -> None:
        """Called by the Isaac main loop once per rendered frame."""

        pending = self._pending
        if pending is None:
            return
        pending.frames_left -= 1
        if pending.frames_left > 0:
            return
        try:
            pending.result = self._capture_on_main(pending.base)
        except BaseException as exc:  # propagate to waiting HTTP request
            pending.error = exc
        finally:
            self._pending = None
            pending.event.set()

    def drain_main_thread(self) -> None:
        """Execute all queued HTTP work; call once per rendered frame."""

        if self._main_thread_id is None:
            self._main_thread_id = threading.get_ident()
        if threading.get_ident() != self._main_thread_id:
            raise RuntimeError("drain_main_thread must run on the Isaac owner thread")
        while True:
            try:
                func, args, event, result = self._main_tasks.get_nowait()
            except queue.Empty:
                return
            try:
                result["value"] = func(*args)
            except BaseException as exc:
                result["error"] = exc
            finally:
                event.set()

    def _call_main(self, func: Any, *args: Any) -> Any:
        if threading.get_ident() == self._main_thread_id:
            return func(*args)
        event = threading.Event()
        result: dict[str, Any] = {}
        self._main_tasks.put((func, args, event, result))
        if not event.wait(timeout=30.0):
            raise TimeoutError("Isaac main thread did not service the request within 30 seconds")
        if "error" in result:
            raise result["error"]
        return result.get("value")

    def _wait_for_capture(self, base: dict[str, Any]) -> dict[str, Any]:
        if self._pending is not None:
            raise RuntimeError("another capture is pending")
        pending = _PendingCapture(event=threading.Event(), base=base)
        self._pending = pending
        if not pending.event.wait(timeout=30.0):
            self._pending = None
            raise TimeoutError("render loop did not produce two frames within 30 seconds")
        if pending.error:
            raise pending.error
        assert pending.result is not None
        return pending.result

    def _set_pose_on_main(self, state: tuple[float, float, int]) -> None:
        x, y, yaw_bin = state
        if self._robot_prim is None:
            raise RuntimeError("robot USD prim is not loaded")
        self._robot_prim.set_world_pose([x, y, 0.0], quat_wxyz_from_yaw(yaw_bin * TURN_RAD))

    def _pose_is_free(self, state: tuple[float, float, int]) -> bool:
        assert self.grid is not None
        cell = self.grid.world_to_cell(state[0], state[1])
        occupied = footprint_cells(
            center=cell,
            yaw_bin=state[2],
            half_length=self.half_length,
            half_width=self.half_width,
            resolution=self.grid.resolution,
        )
        return all(self.grid.is_free(candidate) for candidate in occupied)

    def _capture_on_main(self, base: dict[str, Any]) -> dict[str, Any]:
        if self.episode_id is None:
            raise RuntimeError("capture requested without episode")
        import numpy as np

        rgb = np.asarray(self._rgb_annotator.get_data())
        depth = np.asarray(self._depth_annotator.get_data())
        if rgb.ndim != 3 or rgb.shape[0] != self.height or rgb.shape[1] != self.width:
            raise RuntimeError(f"RGB annotator returned unexpected shape {rgb.shape}")
        if depth.ndim < 2 or depth.shape[0] != self.height or depth.shape[1] != self.width:
            raise RuntimeError(f"depth annotator returned unexpected shape {depth.shape}")
        if rgb.shape[-1] >= 4:
            rgb = rgb[..., :3]
        if not np.isfinite(depth).any():
            raise RuntimeError("depth annotator returned no finite values")
        step_name = f"{self.step_id:04d}"
        episode_dir = self.media_root / self.episode_id
        episode_dir.mkdir(parents=True, exist_ok=True)
        rgb_path = episode_dir / f"{step_name}.jpg"
        depth_path = episode_dir / f"{step_name}.npy"
        self._write_rgb(rgb_path, rgb)
        np.save(depth_path, depth.astype(np.float32), allow_pickle=False)
        distance = math.dist(self.current_pose[:2], self.goal_world)
        response = build_observation(
            episode_id=self.episode_id,
            step_id=self.step_id,
            rgb_path=str(rgb_path.relative_to(self.root)),
            depth_path=str(depth_path.relative_to(self.root)),
            pose_matrix=pose_matrix_xy_yaw(self.current_pose[0], self.current_pose[1], self.current_pose[2] * TURN_RAD),
            distance_to_goal_m=distance,
            collision=base["collision"],
            blocked=base["blocked"],
            terminated=base["terminated"],
            truncated=base["truncated"],
        )
        response.update({"target_id": self.target_id, "target_xy": list(self.goal_world)})
        return response

    @staticmethod
    def _write_rgb(path: Path, rgb: Any) -> None:
        try:
            from PIL import Image

            Image.fromarray(rgb).save(path, format="JPEG", quality=90)
            return
        except Exception as exc:
            raise RuntimeError(f"cannot write RGB JPEG: {type(exc).__name__}") from exc

    def _world_to_cell(self, x: float, y: float) -> tuple[int, int]:
        return round(x / self.resolution), round(y / self.resolution)


__all__ = ["IsaacBackend", "action_pose", "pose_matrix_xy_yaw", "quat_wxyz_from_yaw"]
