#!/usr/bin/env python3
"""Shared bounded I/O for the Herdr worker dispatcher and watcher."""

from __future__ import annotations

import json
import subprocess
import urllib.request


HERDR_TIMEOUT_SECONDS = 30


def herdr(session: str, *args: str) -> subprocess.CompletedProcess[str]:
    command = ["herdr", "--session", session, *args]
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=HERDR_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        return subprocess.CompletedProcess(
            command,
            124,
            stdout=error.stdout or "",
            stderr=f"herdr timed out after {HERDR_TIMEOUT_SECONDS}s",
        )


def parse_headroom_totals(data: object, agent: str) -> tuple[int, int, int]:
    if not isinstance(data, dict):
        raise ValueError("invalid Headroom stats payload")
    usage = data.get("agent_usage")
    if not isinstance(usage, dict):
        summary = data.get("summary")
        usage = summary.get("agent_usage") if isinstance(summary, dict) else None
    agents = usage.get("agents", []) if isinstance(usage, dict) else []
    for current in agents:
        if isinstance(current, dict) and current.get("agent") == agent:
            return (
                int(current.get("requests") or 0),
                int(current.get("after_tokens") or 0),
                int(current.get("output_tokens") or 0),
            )
    return (0, 0, 0)


def headroom_totals(agent: str) -> tuple[int, int, int]:
    with urllib.request.urlopen("http://127.0.0.1:8787/stats", timeout=3) as response:
        return parse_headroom_totals(json.load(response), agent)

