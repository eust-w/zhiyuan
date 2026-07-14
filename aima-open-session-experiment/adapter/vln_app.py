"""GPUFree/GenieSim entrypoint for the loopback non-official adapter.

Run this file with the preinstalled Isaac Python (``/isaac-sim/python.sh``),
not the host Python used for the StreamVLN environment.  The script keeps all
USD and Isaac calls on the main render thread; the HTTP server is a daemon
thread that only waits on APICore's render queue.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from pathlib import Path
from typing import Any


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError("adapter config must be a YAML object")
    return data


def _build_genie_config() -> Any:
    from geniesim.config.params import Config

    cfg = Config()
    cfg.app.headless = True
    cfg.app.enable_ros = False
    cfg.app.enable_curobo = False
    cfg.app.record_img = False
    cfg.app.record_video = False
    cfg.app.enable_pub_depth_camera = False
    cfg.benchmark.task_name = "market_00_g2"
    cfg.benchmark.num_episode = 1
    cfg.layout.seed = 0
    return cfg


def run(adapter_config_path: Path, root: Path) -> None:
    genie_root = Path(__file__).resolve().parents[2]
    # The normal deployment is /root/genie_sim; keeping this override makes
    # the script usable from a copied persistent workspace as well.
    genie_root = Path(__import__("os").environ.get("GENIE_SIM_ROOT", "/root/genie_sim"))
    sys.path.insert(0, str(genie_root / "source"))
    import geniesim.utils.system_utils as system_utils

    system_utils.check_and_fix_env()
    print(json.dumps({"event": "import_app_launcher"}), flush=True)
    from geniesim.app.workflow import AppLauncher

    config = _build_genie_config()
    app_launcher = AppLauncher(config.app)
    simulation_app = app_launcher.app
    print(json.dumps({"event": "simulation_app_ready"}), flush=True)
    # Prime Kit before importing/authoring the world.  The preinstalled
    # launcher otherwise considers a headless app idle and may close it while
    # the runtime USD AABB layer is being projected.
    simulation_app.update()

    # Isaac modules must be imported after SimulationApp is created.
    from isaacsim.core.api import World
    print(json.dumps({"event": "world_imported"}), flush=True)
    print(json.dumps({"event": "genie_imported"}), flush=True)

    from adapter.isaac_backend import IsaacBackend
    from adapter.service import AdapterService

    adapter_config = _load_yaml(adapter_config_path)
    print(json.dumps({"event": "adapter_config_loaded"}), flush=True)
    world = World(
        stage_units_in_meters=1,
        physics_dt=1.0 / config.app.physics_step,
        rendering_dt=1.0 / config.app.rendering_step,
    )
    simulation_app.update()
    backend = IsaacBackend(
        root=root,
        api_core=None,
        world=world,
        adapter_config=adapter_config,
        app_update=simulation_app.update,
    )

    try:
        # This call is intentionally before the render loop: the private API
        # is safe on the owner thread, while the public method would wait for
        # a loop that has not started yet.
        backend.bootstrap_main_thread()
        simulation_app.update()
        print(json.dumps({"event": "backend_bootstrapped"}), flush=True)
        world.play()
        simulation_app.update()
        service = AdapterService(root=root, backend=backend, host="127.0.0.1", port=5802)
        print(json.dumps({"event": "adapter_ready", **backend.health()}, ensure_ascii=False), flush=True)
        server_thread = threading.Thread(target=service.serve_forever, name="aima-http", daemon=True)
        server_thread.start()

        step = 0
        while simulation_app.is_running():
            world.step(render=True)
            backend.drain_main_thread()
            backend.on_frame()
            step += 1
            if step % 600 == 0:
                print(json.dumps({"event": "heartbeat", "frame": step}, ensure_ascii=False), flush=True)
    finally:
        try:
            service.shutdown()  # type: ignore[has-type]
        except Exception:
            pass
        simulation_app.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the non-official GenieSim StreamVLN adapter")
    parser.add_argument("--config", type=Path, required=True, help="nonofficial-market-g2.yaml")
    parser.add_argument("--root", type=Path, required=True, help="persistent experiment root")
    args = parser.parse_args()
    run(args.config.expanduser().resolve(), args.root.expanduser().resolve())


if __name__ == "__main__":
    main()
