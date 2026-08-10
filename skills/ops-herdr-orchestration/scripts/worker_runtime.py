#!/usr/bin/env python3
"""Shared bounded I/O for the Herdr worker dispatcher and watcher."""

from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from dataclasses import dataclass


HERDR_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class HeadroomRequest:
    key: str
    uncached_input_tokens: int
    gross_input_tokens: int
    output_tokens: int


def herdr(
    session: str,
    *args: str,
    timeout_seconds: int = HERDR_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    command = ["herdr", "--session", session, *args]
    env = os.environ.copy()
    env["IPSE_HERDR_DISPATCH"] = "1"
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
        )
    except subprocess.TimeoutExpired as error:
        return subprocess.CompletedProcess(
            command,
            124,
            stdout=error.stdout or "",
            stderr=f"herdr timed out after {timeout_seconds}s",
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


def _request_agent(entry: dict[str, object]) -> str:
    tags = entry.get("tags")
    if isinstance(tags, dict):
        client = tags.get("client")
        if isinstance(client, str):
            return client
    model = str(entry.get("model") or "").lower()
    return "codex" if "gpt-" in model or "codex" in model else ""


def parse_headroom_requests(data: object, agent: str) -> list[HeadroomRequest]:
    """Return recent attributable requests with cache-aware input usage."""
    if not isinstance(data, dict):
        raise ValueError("invalid Headroom stats payload")
    logs = data.get("request_logs")
    if not isinstance(logs, list):
        raise ValueError("Headroom request logs are unavailable")
    requests: list[HeadroomRequest] = []
    for entry in logs:
        if not isinstance(entry, dict) or _request_agent(entry) != agent:
            continue
        request_id = str(entry.get("request_id") or "")
        timestamp = str(entry.get("timestamp") or "")
        if not request_id or not timestamp:
            continue
        gross = int(entry.get("input_tokens_optimized") or 0)
        uncached_value = entry.get("uncached_input_tokens")
        uncached = gross if uncached_value is None else int(uncached_value or 0)
        output = int(entry.get("output_tokens") or 0)
        key = "|".join((request_id, timestamp, str(gross), str(output)))
        requests.append(HeadroomRequest(key, uncached, gross, output))
    return requests


def headroom_requests(agent: str) -> list[HeadroomRequest]:
    with urllib.request.urlopen("http://127.0.0.1:8787/stats", timeout=3) as response:
        return parse_headroom_requests(json.load(response), agent)


def headroom_totals(agent: str) -> tuple[int, int, int]:
    with urllib.request.urlopen("http://127.0.0.1:8787/stats", timeout=3) as response:
        return parse_headroom_totals(json.load(response), agent)
