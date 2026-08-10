#!/usr/bin/env python3
"""Score a measured Headroom/OpenCode trial against adoption gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any


MIN_RUNS = 5
MIN_INPUT_SAVINGS_PCT = 20.0
MAX_WALL_REGRESSION_PCT = 10.0
MAX_OUTPUT_REGRESSION_PCT = 10.0
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_OID_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
TOKEN_SOURCES = {"provider_receipt", "harness_receipt"}


def percentage_change(before: float, after: float) -> float:
    if not math.isfinite(before) or not math.isfinite(after) or before <= 0:
        raise ValueError("baseline total must be positive")
    result = ((after - before) / before) * 100.0
    if not math.isfinite(result):
        raise ValueError("aggregate change must be finite")
    return result


def numeric(run: dict[str, Any], side: str, field: str) -> float:
    value = run[side][field]
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(f"{side}.{field} must be a finite non-negative number")
    return float(value)


def integer(run: dict[str, Any], side: str, field: str) -> int:
    value = run[side][field]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{side}.{field} must be a non-negative integer")
    return value


def valid_digest(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


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
    if not valid_digest(payload.get("concurrency_receipt_sha256")):
        failures.append("concurrency drill receipt digest is invalid")
    if payload.get("direct_bypass_after_proxy_stop") is not True:
        failures.append("direct bypass after proxy failure not proven")
    if not valid_digest(payload.get("direct_bypass_receipt_sha256")):
        failures.append("direct-bypass drill receipt digest is invalid")
    if len(runs) < MIN_RUNS:
        failures.append(f"at least {MIN_RUNS} runs")

    baseline_input = candidate_input = 0.0
    baseline_output = candidate_output = 0.0
    baseline_wall = candidate_wall = 0.0

    for index, run in enumerate(runs):
        if not isinstance(run, dict):
            failures.append(f"run-{index + 1}: run must be an object")
            continue
        name = run.get("name") or f"run-{index + 1}"
        try:
            accept_command = run.get("accept_command")
            if not isinstance(accept_command, str) or not accept_command.strip():
                failures.append(f"{name}: acceptance command is missing")
            elif not valid_digest(run.get("accept_command_sha256")):
                failures.append(f"{name}: acceptance command digest is invalid")
            elif run["accept_command_sha256"] != digest(accept_command):
                failures.append(f"{name}: acceptance command digest does not match")
            if not isinstance(run.get("model"), str) or not run["model"].strip():
                failures.append(f"{name}: model is missing")
            if not isinstance(run.get("starting_commit"), str) or not GIT_OID_RE.fullmatch(
                run["starting_commit"]
            ):
                failures.append(f"{name}: starting commit is invalid")
            if not valid_digest(run.get("task_brief_sha256")):
                failures.append(f"{name}: task brief digest is invalid")
            if run.get("token_source") not in TOKEN_SOURCES:
                failures.append(f"{name}: token source must be a provider or harness receipt")
            before_hash = run.get("config_sha256_before")
            after_hash = run.get("config_sha256_after")
            if not valid_digest(before_hash) or not valid_digest(after_hash):
                failures.append(f"{name}: configuration hashes are invalid")
            elif before_hash != after_hash:
                failures.append(f"{name}: persistent config changed")
            for side in ("baseline", "candidate"):
                side_data = run.get(side)
                if not isinstance(side_data, dict) or not valid_digest(
                    side_data.get("token_receipt_sha256")
                ):
                    failures.append(f"{name}: {side} token receipt digest is invalid")

            baseline_exit = integer(run, "baseline", "accept_exit")
            candidate_exit = integer(run, "candidate", "accept_exit")
            baseline_prompts = integer(run, "baseline", "worker_prompts")
            candidate_prompts = integer(run, "candidate", "worker_prompts")
            baseline_retries = integer(run, "baseline", "retries")
            candidate_retries = integer(run, "candidate", "retries")
            baseline_run_input = numeric(run, "baseline", "uncached_input_tokens")
            candidate_run_input = numeric(run, "candidate", "uncached_input_tokens")
            baseline_run_wall = numeric(run, "baseline", "wall_seconds")
            candidate_run_wall = numeric(run, "candidate", "wall_seconds")
            baseline_run_output = numeric(run, "baseline", "output_tokens")
            candidate_run_output = numeric(run, "candidate", "output_tokens")

            if baseline_exit != 0:
                failures.append(f"{name}: baseline acceptance failed")
            if candidate_exit != 0:
                failures.append(f"{name}: candidate acceptance failed")
            if baseline_prompts != 1:
                failures.append(f"{name}: baseline worker prompt count is not one")
            if candidate_prompts != 1:
                failures.append(f"{name}: candidate worker prompt count is not one")
            if baseline_retries != 0:
                failures.append(f"{name}: baseline retry count is not zero")
            if candidate_retries != 0:
                failures.append(f"{name}: candidate retry count is not zero")

            baseline_input += baseline_run_input
            candidate_input += candidate_run_input
            baseline_output += baseline_run_output
            candidate_output += candidate_run_output
            baseline_wall += baseline_run_wall
            candidate_wall += candidate_run_wall
        except (KeyError, TypeError, ValueError) as error:
            failures.append(f"{name}: invalid metrics: {error}")

    input_savings_pct = output_regression_pct = wall_regression_pct = None
    try:
        input_savings_pct = -percentage_change(baseline_input, candidate_input)
        if input_savings_pct < MIN_INPUT_SAVINGS_PCT:
            failures.append("uncached input savings below 20%")
    except ValueError:
        failures.append("aggregate baseline input must be positive")

    try:
        output_regression_pct = percentage_change(baseline_output, candidate_output)
        if output_regression_pct > MAX_OUTPUT_REGRESSION_PCT:
            failures.append("output-token regression above 10%")
    except ValueError:
        failures.append("aggregate baseline output must be positive")

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
            "output_regression_pct": (
                round(output_regression_pct, 2) if output_regression_pct is not None else None
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
        payload = json.loads(
            args.results.read_text(encoding="utf-8"), parse_constant=reject_json_constant
        )
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
