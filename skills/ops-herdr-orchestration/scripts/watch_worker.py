#!/usr/bin/env python3
"""Supervise one Herdr worker and interrupt it at deterministic limits."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time


def herdr(session: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["herdr", "--session", session, *args],
        check=False,
        capture_output=True,
        text=True,
    )


def status(session: str, agent: str) -> str:
    result = herdr(session, "agent", "get", agent)
    if result.returncode:
        return "missing"
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return "unknown"
    return str(data.get("agent_status") or data.get("status") or "unknown").lower()


def screen_digest(session: str, agent: str) -> str:
    result = herdr(session, "agent", "read", agent, "--source", "recent-unwrapped", "--lines", "120")
    return hashlib.sha256(result.stdout.encode()).hexdigest() if result.returncode == 0 else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True, choices=("ipse", "biz", "work"))
    parser.add_argument("--agent", required=True)
    parser.add_argument("--max-seconds", type=int, default=600)
    parser.add_argument("--idle-seconds", type=int, default=300)
    parser.add_argument("--poll-seconds", type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.max_seconds <= 1200:
        parser.error("--max-seconds must be 1..1200")
    started = time.monotonic()
    last_digest = ""
    last_change = started
    while True:
        current = status(args.session, args.agent)
        elapsed = int(time.monotonic() - started)
        if current in {"done", "idle", "blocked", "error", "failed", "missing"}:
            print(json.dumps({"agent": args.agent, "status": current, "elapsed_seconds": elapsed, "interrupted": False}))
            return 0 if current in {"done", "idle"} else 1
        digest = screen_digest(args.session, args.agent)
        now = time.monotonic()
        if digest and digest != last_digest:
            last_digest, last_change = digest, now
        reason = None
        if elapsed >= args.max_seconds:
            reason = "wall_limit"
        elif last_digest and now - last_change >= args.idle_seconds:
            reason = "idle_limit"
        if reason:
            herdr(args.session, "agent", "send-keys", args.agent, "ctrl+c")
            print(json.dumps({"agent": args.agent, "status": current, "elapsed_seconds": elapsed, "interrupted": True, "reason": reason}))
            return 2
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
