#!/usr/bin/env python3
"""Supervise one Herdr worker and interrupt it at deterministic limits."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import re
import time

from worker_runtime import headroom_requests, herdr


def parse_status(data: object) -> str:
    if not isinstance(data, dict):
        return "unknown"
    result = data.get("result")
    agent = result.get("agent") if isinstance(result, dict) else None
    nested = agent.get("agent_status") if isinstance(agent, dict) else None
    return str(nested or data.get("agent_status") or data.get("status") or "unknown").lower()


def status(session: str, agent: str) -> str:
    result = herdr(session, "agent", "get", agent)
    if result.returncode:
        return "missing"
    try:
        return parse_status(json.loads(result.stdout))
    except json.JSONDecodeError:
        return "unknown"


def screen_output(session: str, agent: str) -> str:
    result = herdr(session, "agent", "read", agent, "--source", "recent-unwrapped", "--lines", "120")
    return result.stdout if result.returncode == 0 else ""


def usage_limit_reason(
    deltas: dict[str, int],
    max_requests: int,
    max_uncached_input_tokens: int,
    max_output_tokens: int,
) -> str | None:
    if deltas["requests"] >= max_requests:
        return "request_limit"
    if deltas["uncached_input_tokens"] >= max_uncached_input_tokens:
        return "uncached_input_token_limit"
    if deltas["output_tokens"] >= max_output_tokens:
        return "output_token_limit"
    return None


def add_new_requests(agent: str, seen: set[str], deltas: dict[str, int]) -> None:
    for request in headroom_requests(agent):
        if request.key in seen:
            continue
        seen.add(request.key)
        deltas["requests"] += 1
        deltas["uncached_input_tokens"] += request.uncached_input_tokens
        deltas["gross_input_tokens"] += request.gross_input_tokens
        deltas["output_tokens"] += request.output_tokens


FAILURE_RE = re.compile(r"\b(error|failed|failure|exception|traceback|timed? out|not found|denied|unauthorized)\b", re.I)
VOLATILE_RE = re.compile(r"\b(?:0x)?[0-9a-f]{6,}|\b\d+\b", re.I)


def repeated_failure_signature(output: str) -> str | None:
    counts: Counter[str] = Counter()
    for raw_line in output.splitlines():
        line = " ".join(raw_line.split()).lower()
        if not line or not FAILURE_RE.search(line):
            continue
        signature = VOLATILE_RE.sub("#", line)[:200]
        counts[signature] += 1
        if counts[signature] >= 3:
            return signature
    return None


def idle_limit_reached(last_change: float, now: float, idle_seconds: int) -> bool:
    return now - last_change >= idle_seconds


def interrupt(session: str, agent: str) -> None:
    herdr(session, "agent", "send-keys", agent, "ctrl+c")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True, choices=("ipse", "biz", "work"))
    parser.add_argument("--agent", required=True)
    parser.add_argument("--max-seconds", type=int, default=480)
    parser.add_argument("--idle-seconds", type=int, default=120)
    parser.add_argument("--poll-seconds", type=int, default=2)
    parser.add_argument("--max-requests", type=int, default=8)
    parser.add_argument("--max-uncached-input-tokens", type=int, default=80000)
    parser.add_argument("--max-output-tokens", type=int, default=8000)
    parser.add_argument("--headroom-agent", choices=("opencode", "codex"))
    parser.add_argument("--baseline-request-key", action="append", default=[])
    args = parser.parse_args()
    if not 1 <= args.max_seconds <= 1200:
        parser.error("--max-seconds must be 1..1200")
    started = time.monotonic()
    last_digest = ""
    last_change = started
    usage_failures = 0
    unknown_statuses = 0
    deltas = {
        "requests": 0,
        "uncached_input_tokens": 0,
        "gross_input_tokens": 0,
        "output_tokens": 0,
    }
    seen = set(args.baseline_request_key)
    while True:
        current = status(args.session, args.agent)
        elapsed = int(time.monotonic() - started)
        if current in {"blocked", "error", "failed", "missing"}:
            print(json.dumps({"agent": args.agent, "status": current, "elapsed_seconds": elapsed, "interrupted": False}))
            return 1
        unknown_statuses = unknown_statuses + 1 if current == "unknown" else 0
        output = screen_output(args.session, args.agent)
        digest = hashlib.sha256(output.encode()).hexdigest() if output else ""
        now = time.monotonic()
        if digest and digest != last_digest:
            last_digest, last_change = digest, now
        reason = None
        if elapsed >= args.max_seconds:
            reason = "wall_limit"
        elif idle_limit_reached(last_change, now, args.idle_seconds):
            reason = "idle_limit"
        elif repeated_failure_signature(output):
            reason = "repeated_failure"
        elif unknown_statuses >= 3:
            reason = "status_unavailable"
        usage_checked = not args.headroom_agent
        if not reason and args.headroom_agent:
            try:
                add_new_requests(args.headroom_agent, seen, deltas)
                usage_failures = 0
                usage_checked = True
                reason = usage_limit_reason(
                    deltas,
                    args.max_requests,
                    args.max_uncached_input_tokens,
                    args.max_output_tokens,
                )
            except (OSError, ValueError, json.JSONDecodeError):
                usage_failures += 1
                if usage_failures >= 3:
                    reason = "usage_unavailable"
        if not reason and current in {"done", "idle"}:
            if not usage_checked:
                time.sleep(min(args.poll_seconds, 5))
                continue
            receipt_seen = bool(re.search(r"(?im)^\s*(accepted|blocked)\s*:", output))
            if not receipt_seen and elapsed < min(10, args.max_seconds):
                time.sleep(min(args.poll_seconds, 5))
                continue
            print(json.dumps({"agent": args.agent, "status": current, "elapsed_seconds": elapsed, "interrupted": False}))
            return 0
        if reason:
            interrupt(args.session, args.agent)
            payload = {"agent": args.agent, "status": current, "elapsed_seconds": elapsed, "interrupted": True, "reason": reason}
            if args.headroom_agent:
                payload["usage"] = deltas
            print(json.dumps(payload))
            return 2
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
