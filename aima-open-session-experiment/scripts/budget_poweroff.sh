#!/usr/bin/env bash
set -euo pipefail

seconds="${1:?usage: budget_poweroff.sh SECONDS EVIDENCE_LOG}"
evidence_log="${2:?usage: budget_poweroff.sh SECONDS EVIDENCE_LOG}"
mkdir -p "$(dirname "$evidence_log")"
exec >>"$evidence_log" 2>&1
printf '{"event":"budget_timer_armed","seconds":%s,"armed_at":"%s"}\n' "$seconds" "$(date --iso-8601=seconds)"
sleep "$seconds"
printf '{"event":"budget_timer_fired","fired_at":"%s"}\n' "$(date --iso-8601=seconds)"
poweroff
