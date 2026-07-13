"""Stage 0 loopback keyboard client; backward never enters StreamVLN data."""

from __future__ import annotations

import argparse
import json
import sys
import termios
import time
import tty
from typing import Any
from urllib.request import Request, urlopen


KEY_ACTIONS = {"w": 1, "s": 4, "a": 2, "d": 3, " ": 0}


def request_json(base_url: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = Request(
        base_url.rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def keys(sequence: str | None):
    if sequence is not None:
        yield from sequence.lower()
        return
    if not sys.stdin.isatty():
        raise RuntimeError("interactive keyboard control requires a TTY or --sequence")
    original = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        while True:
            yield sys.stdin.read(1).lower()
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, original)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:5802")
    parser.add_argument("--episode-id", default="stage0-keyboard")
    parser.add_argument("--seed", type=int, default=4001)
    parser.add_argument("--sequence", default=None, help="non-interactive evidence sequence, e.g. 'wsad '")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    reset = request_json(
        args.base_url,
        "/v1/episodes/reset",
        {
            "schema_version": "geniesim-streamvln/v1",
            "episode_id": args.episode_id,
            "seed": args.seed,
            "instruction": "Stage 0 keyboard validation only.",
            "target_id": "red-target-marker",
        },
    )
    records = [{"key": "reset", "action_id": -1, "observation": reset}]
    print("W forward | S backward(debug only) | A left | D right | Space stop | Q quit", flush=True)
    for index, key in enumerate(keys(args.sequence), start=1):
        if key == "q":
            break
        if key not in KEY_ACTIONS:
            continue
        action = KEY_ACTIONS[key]
        observation = request_json(
            args.base_url,
            f"/v1/debug/episodes/{args.episode_id}/step",
            {"request_id": f"keyboard-{index:04d}", "action_id": action},
        )
        records.append({"key": "Space" if key == " " else key.upper(), "action_id": action, "observation": observation})
        print(json.dumps({"key": records[-1]["key"], "step": observation["step_id"], "blocked": observation["blocked"]}), flush=True)
        if observation.get("terminated"):
            break
        time.sleep(0.05)
    request_json(args.base_url, f"/v1/episodes/{args.episode_id}/close", {})
    if args.output:
        from pathlib import Path

        Path(args.output).write_text(json.dumps({"stage": 0, "records": records}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
