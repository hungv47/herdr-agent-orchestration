#!/usr/bin/env python3
"""Audit one Hermes captain session for enforced orchestration waste limits."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


API_RE = re.compile(r"API call #\d+:.*? in=(\d+) out=(\d+)")
WRITE_RE = re.compile(r"tool (?:patch|write_file) completed")


def audit(path: Path, session: str, max_calls_per_turn: int, orchestrated: bool) -> dict[str, object]:
    marker = f"[{session}]"
    turns: list[int] = []
    current_calls = 0
    input_tokens = 0
    output_tokens = 0
    write_calls = 0
    background_reviews = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if marker not in line:
            continue
        if "turn_context: conversation turn:" in line:
            if current_calls:
                turns.append(current_calls)
            current_calls = 0
        match = API_RE.search(line)
        if match:
            current_calls += 1
            input_tokens += int(match.group(1))
            output_tokens += int(match.group(2))
        if WRITE_RE.search(line):
            write_calls += 1
        if "bg-review" in line:
            background_reviews += 1
    if current_calls:
        turns.append(current_calls)
    violations: list[str] = []
    max_calls = max(turns, default=0)
    if max_calls > max_calls_per_turn:
        violations.append(f"max_calls_per_turn={max_calls}>{max_calls_per_turn}")
    if background_reviews:
        violations.append(f"background_reviews={background_reviews}>0")
    if orchestrated and write_calls:
        violations.append(f"captain_write_calls={write_calls}>0")
    return {
        "status": "fail" if violations else "pass",
        "session": session,
        "metrics": {
            "turns": len(turns),
            "calls_by_turn": turns,
            "max_calls_per_turn": max_calls,
            "cumulative_input_tokens": input_tokens,
            "cumulative_output_tokens": output_tokens,
            "background_reviews": background_reviews,
            "captain_write_calls": write_calls,
        },
        "limits": {"max_calls_per_turn": max_calls_per_turn, "background_reviews": 0},
        "violations": violations,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("--session", required=True)
    parser.add_argument("--max-calls-per-turn", type=int, default=8)
    parser.add_argument("--orchestrated", action="store_true")
    args = parser.parse_args()
    result = audit(args.log, args.session, args.max_calls_per_turn, args.orchestrated)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
