#!/usr/bin/env python3
"""Audit one Hermes captain session for enforced orchestration waste limits."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import re
from pathlib import Path


API_RE = re.compile(r"API call #\d+:.*? in=(\d+) out=(\d+)")
TOOL_RE = re.compile(r"agent\.tool_executor: (?:tool|Tool) ([\w-]+) (?:completed|returned error)")
WRITE_RE = re.compile(r"tool (?:patch|write_file) completed", re.I)
RAW_HERDR_RE = re.compile(
    r"\bherdr\b.*?\b(?:agent\s+(?:start|prompt|send-keys)|"
    r"pane\s+(?:split|close|run|send-text|send-keys)|"
    r"session\s+(?:stop|delete)|integration\s+(?:install|uninstall))\b",
    re.I,
)
TIMESTAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(?:,\d+)?")


def audit(
    path: Path,
    session: str,
    max_calls_per_turn: int,
    max_total_calls: int,
    max_input_tokens: int,
    max_output_tokens: int,
    max_duration_seconds: int,
    max_tool_calls: int,
    max_terminal_calls: int,
    orchestrated: bool,
) -> dict[str, object]:
    marker = f"[{session}]"
    turns: list[int] = []
    current_calls = 0
    total_calls = 0
    input_tokens = 0
    output_tokens = 0
    tool_calls = 0
    terminal_calls = 0
    write_calls = 0
    raw_herdr_calls = 0
    background_reviews = 0
    timestamps: list[datetime] = []

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if marker not in line:
            continue
        timestamp = TIMESTAMP_RE.match(line)
        if timestamp:
            timestamps.append(datetime.strptime(timestamp.group(1), "%Y-%m-%d %H:%M:%S"))
        if "turn_context: conversation turn:" in line:
            if current_calls:
                turns.append(current_calls)
            current_calls = 0
        match = API_RE.search(line)
        if match:
            current_calls += 1
            total_calls += 1
            input_tokens += int(match.group(1))
            output_tokens += int(match.group(2))
        tool = TOOL_RE.search(line)
        if tool:
            tool_calls += 1
            if tool.group(1).lower() in {"terminal", "shell", "bash"}:
                terminal_calls += 1
        if WRITE_RE.search(line):
            write_calls += 1
        if RAW_HERDR_RE.search(line):
            raw_herdr_calls += 1
        if "bg-review" in line:
            background_reviews += 1
    if current_calls:
        turns.append(current_calls)

    duration_seconds = (
        int((timestamps[-1] - timestamps[0]).total_seconds()) if len(timestamps) > 1 else 0
    )
    violations: list[str] = []
    max_calls = max(turns, default=0)
    if max_calls > max_calls_per_turn:
        violations.append(f"max_calls_per_turn={max_calls}>{max_calls_per_turn}")
    if total_calls > max_total_calls:
        violations.append(f"total_api_calls={total_calls}>{max_total_calls}")
    if input_tokens > max_input_tokens:
        violations.append(f"input_tokens={input_tokens}>{max_input_tokens}")
    if output_tokens > max_output_tokens:
        violations.append(f"output_tokens={output_tokens}>{max_output_tokens}")
    if duration_seconds > max_duration_seconds:
        violations.append(f"duration_seconds={duration_seconds}>{max_duration_seconds}")
    if tool_calls > max_tool_calls:
        violations.append(f"tool_calls={tool_calls}>{max_tool_calls}")
    if terminal_calls > max_terminal_calls:
        violations.append(f"terminal_calls={terminal_calls}>{max_terminal_calls}")
    if background_reviews:
        violations.append(f"background_reviews={background_reviews}>0")
    if raw_herdr_calls:
        violations.append(f"raw_herdr_mutations={raw_herdr_calls}>0")
    if orchestrated and write_calls:
        violations.append(f"captain_write_calls={write_calls}>0")

    return {
        "session": session,
        "status": "fail" if violations else "pass",
        "metrics": {
            "turns": len(turns),
            "api_calls": total_calls,
            "max_calls_per_turn": max_calls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "duration_seconds": duration_seconds,
            "tool_calls": tool_calls,
            "terminal_calls": terminal_calls,
            "captain_write_calls": write_calls,
            "raw_herdr_mutations": raw_herdr_calls,
            "background_reviews": background_reviews,
        },
        "limits": {
            "max_calls_per_turn": max_calls_per_turn,
            "max_total_calls": max_total_calls,
            "max_input_tokens": max_input_tokens,
            "max_output_tokens": max_output_tokens,
            "max_duration_seconds": max_duration_seconds,
            "max_tool_calls": max_tool_calls,
            "max_terminal_calls": max_terminal_calls,
        },
        "violations": violations,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("--session", required=True)
    parser.add_argument("--max-calls-per-turn", type=int, default=8)
    parser.add_argument("--max-total-calls", type=int, default=8)
    parser.add_argument("--max-input-tokens", type=int, default=400_000)
    parser.add_argument("--max-output-tokens", type=int, default=12_000)
    parser.add_argument("--max-duration-seconds", type=int, default=900)
    parser.add_argument("--max-tool-calls", type=int, default=12)
    parser.add_argument("--max-terminal-calls", type=int, default=3)
    parser.add_argument("--orchestrated", action="store_true")
    args = parser.parse_args()
    result = audit(
        args.log,
        args.session,
        args.max_calls_per_turn,
        args.max_total_calls,
        args.max_input_tokens,
        args.max_output_tokens,
        args.max_duration_seconds,
        args.max_tool_calls,
        args.max_terminal_calls,
        args.orchestrated,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
