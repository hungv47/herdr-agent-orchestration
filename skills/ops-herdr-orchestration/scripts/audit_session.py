#!/usr/bin/env python3
"""Audit a Pi-style JSONL transcript against orchestration budgets."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


def parse_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def text_size(content: object) -> int:
    if not isinstance(content, list):
        return 0
    return sum(
        len(str(item.get("text", "")))
        for item in content
        if isinstance(item, dict) and item.get("type") == "text"
    )


def audit(path: Path, args: argparse.Namespace) -> dict[str, object]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    messages = [row for row in rows if row.get("type") == "message"]
    prompts = [row for row in messages if row.get("message", {}).get("role") == "user"]
    assistants = [row for row in messages if row.get("message", {}).get("role") == "assistant"]
    tools: Counter[str] = Counter()
    usage = Counter()
    cost = 0.0
    for row in assistants:
        message = row.get("message", {})
        for item in message.get("content", []):
            if isinstance(item, dict) and item.get("type") == "toolCall":
                tools[str(item.get("name") or "unknown")] += 1
        current = message.get("usage") or {}
        for key in ("input", "output", "cacheRead", "cacheWrite"):
            usage[key] += int(current.get(key) or 0)
        cost += float((current.get("cost") or {}).get("total") or 0)
    times = [value for row in rows if (value := parse_time(row.get("timestamp")))]
    wall = int((max(times) - min(times)).total_seconds()) if len(times) > 1 else 0
    metrics = {
        "file": str(path),
        "wall_seconds": wall,
        "prompt_messages": len(prompts),
        "prompt_characters": sum(text_size(row.get("message", {}).get("content")) for row in prompts),
        "assistant_turns": len(assistants),
        "tool_calls": sum(tools.values()),
        "tools": dict(tools.most_common()),
        "input_tokens": usage["input"],
        "output_tokens": usage["output"],
        "cache_read_tokens": usage["cacheRead"],
        "cost_usd": round(cost, 6),
    }
    limits = {
        "wall_seconds": args.max_seconds,
        "prompt_messages": args.max_prompts,
        "prompt_characters": args.max_prompt_chars,
        "tool_calls": args.max_tools,
        "input_tokens": args.max_input_tokens,
        "output_tokens": args.max_output_tokens,
    }
    violations = [f"{name}={metrics[name]}>{limit}" for name, limit in limits.items() if metrics[name] > limit]
    return {"status": "fail" if violations else "pass", "metrics": metrics, "limits": limits, "violations": violations}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("transcript", type=Path)
    parser.add_argument("--max-seconds", type=int, default=600)
    parser.add_argument("--max-prompts", type=int, default=2)
    parser.add_argument("--max-prompt-chars", type=int, default=2400)
    parser.add_argument("--max-tools", type=int, default=40)
    parser.add_argument("--max-input-tokens", type=int, default=80000)
    parser.add_argument("--max-output-tokens", type=int, default=20000)
    args = parser.parse_args()
    result = audit(args.transcript, args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
