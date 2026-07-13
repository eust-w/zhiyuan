#!/usr/bin/env bash
set -euo pipefail

project_root="${PROJECT_ROOT:-/root/gpufree-data/zhiyuan-aima/workspace/aima-open-session-experiment}"
run_dir="${RUN_DIR:-/root/gpufree-data/zhiyuan-aima/runs/2026-07-14}"
mkdir -p "$run_dir"
cd "$project_root"
export PYTHONPATH="$project_root"
export SIM_REPO_ROOT="${GENIE_SIM_ROOT:-/root/genie_sim}"
export ROS_DISTRO=jazzy
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}:/isaac-sim/exts/isaacsim.ros2.bridge/jazzy/lib"
exec >>"$run_dir/stage0-adapter.log" 2>&1
printf '{"event":"stage0_launch","started_at":"%s","project_root":"%s"}\n' "$(date --iso-8601=seconds)" "$project_root"
exec /isaac-sim/python.sh -m adapter.vln_app \
  --config "$project_root/configs/nonofficial-market-g2.yaml" \
  --root "$project_root"
