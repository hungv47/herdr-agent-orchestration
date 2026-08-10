#!/usr/bin/env python3
"""Score a measured Headroom/OpenCode trial against adoption gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


MIN_RUNS = 5
MIN_INPUT_SAVINGS_PCT = 20.0
MAX_WALL_REGRESSION_PCT = 10.0


def percentage_change(before: float, after: float) -> float:
    if before <= 0:
        raise ValueError("baseline total must be positive")
    return ((after - before) / before) * 100.0


def numeric(run: dict[str, Any], side: str, field: str) -> float:
    value = run[side][field]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{side}.{field} must be a non-negative number")
    return float(value)


def evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    runs = payload.get("runs")
    if not isinstance(runs, list):
        runs = []
        failures.append("runs must be a list")

    if payload.get("route") != "opencode":
        failures.append("trial route must be opencode")
    if not payload.get("headroom_version"):
        failures.append("headroom version is missing")
    if payload.get("concurrency_survives_owner_exit") is not True:
        failures.append("concurrent-session survival not proven")
    if payload.get("direct_bypass_after_proxy_stop") is not True:
        failures.append("direct bypass after proxy failure not proven")
    if len(runs) < MIN_RUNS:
        failures.append(f"at least {MIN_RUNS} runs")

    baseline_input = candidate_input = 0.0
    baseline_wall = candidate_wall = 0.0

    for index, run in enumerate(runs):
        if not isinstance(run, dict):
            failures.append(f"run-{index + 1}: run must be an object")
            continue
        name = run.get("name") or f"run-{index + 1}"
        try:
            if not run.get("accept_command"):
                failures.append(f"{name}: acceptance command is missing")
            if not run.get("token_source"):
                failures.append(f"{name}: token source is missing")
            before_hash = run.get("config_sha256_before")
            after_hash = run.get("config_sha256_after")
            if not before_hash or not after_hash:
                failures.append(f"{name}: configuration hashes are missing")
            elif before_hash != after_hash:
                failures.append(f"{name}: persistent config changed")

            baseline_exit = numeric(run, "baseline", "accept_exit")
            candidate_exit = numeric(run, "candidate", "accept_exit")
            baseline_prompts = numeric(run, "baseline", "worker_prompts")
            candidate_prompts = numeric(run, "candidate", "worker_prompts")
            baseline_retries = numeric(run, "baseline", "retries")
            candidate_retries = numeric(run, "candidate", "retries")
            baseline_run_input = numeric(run, "baseline", "uncached_input_tokens")
            candidate_run_input = numeric(run, "candidate", "uncached_input_tokens")
            baseline_run_wall = numeric(run, "baseline", "wall_seconds")
            candidate_run_wall = numeric(run, "candidate", "wall_seconds")
            numeric(run, "baseline", "output_tokens")
            numeric(run, "candidate", "output_tokens")

            if baseline_exit != 0:
                failures.append(f"{name}: baseline acceptance failed")
            if candidate_exit != 0:
                failures.append(f"{name}: candidate acceptance failed")
            if baseline_prompts > 1:
                failures.append(f"{name}: baseline used more than one worker prompt")
            if candidate_prompts > 1:
                failures.append(f"{name}: candidate used more than one worker prompt")
            if baseline_retries > 0:
                failures.append(f"{name}: baseline retried")
            if candidate_retries > 0:
                failures.append(f"{name}: candidate retried")

            baseline_input += baseline_run_input
            candidate_input += candidate_run_input
            baseline_wall += baseline_run_wall
            candidate_wall += candidate_run_wall
        except (KeyError, TypeError, ValueError) as error:
            failures.append(f"{name}: invalid metrics: {error}")

    input_savings_pct = wall_regression_pct = None
    try:
        input_savings_pct = -percentage_change(baseline_input, candidate_input)
        if input_savings_pct < MIN_INPUT_SAVINGS_PCT:
            failures.append("uncached input savings below 20%")
    except ValueError:
        failures.append("aggregate baseline input must be positive")

    try:
        wall_regression_pct = percentage_change(baseline_wall, candidate_wall)
        if wall_regression_pct > MAX_WALL_REGRESSION_PCT:
            failures.append("wall-time regression above 10%")
    except ValueError:
        failures.append("aggregate baseline wall time must be positive")

    failures = list(dict.fromkeys(failures))
    return {
        "adopt": not failures,
        "status": "pass" if not failures else "fail",
        "metrics": {
            "runs": len(runs),
            "uncached_input_savings_pct": (
                round(input_savings_pct, 2) if input_savings_pct is not None else None
            ),
            "wall_regression_pct": (
                round(wall_regression_pct, 2) if wall_regression_pct is not None else None
            ),
        },
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path, help="trial results JSON")
    args = parser.parse_args()

    try:
        payload = json.loads(args.results.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("top-level JSON must be an object")
        report = evaluate(payload)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(json.dumps({"adopt": False, "status": "invalid", "error": str(error)}))
        return 2

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["adopt"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
