---
name: ops-herdr-orchestration
description: "Use when choosing DIY vs Herdr, briefing or supervising Herdr workers, preventing retry loops, or auditing orchestration token efficiency."
version: 3.0.0
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [herdr, orchestration, headroom, token-efficiency]
---

# Herdr orchestration

Binding policy: the repository root `AGENTS.md`.

## Choose the cheaper path

- Prefer DIY for small, cohesive, borderline, or read-mostly work.
- Orchestrate only when independent workstreams, specialization, risk, or duration repay dispatch and verification.
- In orchestrate mode the captain stays the sole user contact and performs no task writes.

## Runtime gate

Before dispatch, require healthy Headroom and an existing Herdr session. Use OpenCode DeepSeek first, Cline DeepSeek only as fallback or a disjoint second free lane, and Pi GPT only with a capability reason.

Every worker starts through `scripts/dispatch_worker.py`. It locks the deliverable and harness lane, creates one pane, sends one brief, supervises the worker, verifies that exact pane is gone, and returns one `accepted|blocked` receipt. The lane lock prevents parallel workers from charging one another's Headroom counters. The installed `herdr-guard` mechanically blocks raw mutations.

## Compact bridge

The brief is at most 1,200 characters and has exactly five lines:

1. `role=worker; outcome=` one finished result.
2. `write=` exact paths; all other paths are read-only.
3. `non-goals=` exclusions and external-action limits.
4. `accept=` commands or observable checks.
5. `return=accepted|blocked: paths=<...>; checks=<...>; blocker=<...>; then stop`.

Workers do not delegate, narrate progress, write plans, or perform discovery the captain can do read-only.

## Hard budgets

Defaults per worker: five minutes, 90 idle seconds, five model requests, 50k uncached input tokens, 5k output tokens, and one prompt. The substantial tier requires one-line justification and allows 10 minutes, eight requests, 90k uncached input, and 10k output. Headroom's shared backstop is $5 per day, 60k TPM, 10 RPM, three concurrent connections, one upstream attempt, and a three-minute request timeout unless explicitly overridden.

Headroom request logs attribute uncached and gross input separately: uncached input is the cost ceiling; replayed cached context is reported, not miscounted as new work. A blocked receipt ends the attempt without fallback, correction, infrastructure repair, or replay.

## Captain ceiling

Configure Hermes for eight model iterations per user turn, 12 code-execution tool calls, aggressive loop stops, and zero automatic memory/skill-review nudges. One orchestration turn performs preflight, one synchronous dispatcher call, one read-only verification, and the report. The captain performs no product or orchestration-infrastructure writes while orchestrating.

## Captain loop

1. Select mode and session; check Headroom.
2. Define the fewest whole deliverables and five-line bridge.
3. Run `dispatch_worker.py` once.
4. Verify an accepted receipt read-only; otherwise report blocked immediately.
5. Report outcomes and checks.

Use `scripts/audit_session.py` for a suspect worker JSONL transcript and `scripts/audit_hermes_session.py` for a Hermes captain log. Both exit nonzero on waste.
