#!/usr/bin/env bash
set -euo pipefail

split="${1:?usage: run_collection.sh SPLIT START_SEED COUNT}"
start_seed="${2:?usage: run_collection.sh SPLIT START_SEED COUNT}"
count="${3:?usage: run_collection.sh SPLIT START_SEED COUNT}"
project_root="${PROJECT_ROOT:-/root/gpufree-data/zhiyuan-aima/workspace/aima-open-session-experiment}"
dataset_root="${DATASET_ROOT:-$project_root/dataset-v3}"
run_dir="${RUN_DIR:-/root/gpufree-data/zhiyuan-aima/runs/2026-07-14}"
mkdir -p "$run_dir"
cd "$project_root"
export PYTHONPATH="$project_root"
exec >>"$run_dir/stage1-${split}.log" 2>&1
printf '{"event":"collection_launch","split":"%s","start_seed":%s,"count":%s,"started_at":"%s"}\n' \
  "$split" "$start_seed" "$count" "$(date --iso-8601=seconds)"
python3 -m adapter.collect_dataset \
  --root "$project_root" \
  --dataset-root "$dataset_root" \
  --split "$split" \
  --start-seed "$start_seed" \
  --count "$count"
printf '{"event":"collection_complete","split":"%s","completed_at":"%s"}\n' "$split" "$(date --iso-8601=seconds)"
