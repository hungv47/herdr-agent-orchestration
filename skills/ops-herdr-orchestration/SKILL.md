---
name: ops-herdr-orchestration
description: "Use when choosing DIY vs Herdr, briefing or supervising Herdr workers, preventing retry loops, or auditing orchestration token efficiency."
version: 6.2.0
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [herdr, orchestration, headroom, token-efficiency, ipse, biz, work]
---

# Herdr orchestration

Binding policy: `AGENTS.md`.

## Choose the cheaper execution path

- DIY for small, cohesive, borderline, or read-mostly work.
- Orchestrate only when independent workstreams, specialization, risk, or duration repay dispatch and verification overhead.
- Keep the selected mode for the same scope. A stalled worker never changes it.
- In orchestrate mode the captain stays the sole user contact and performs no task writes.

## Runtime gate

All orchestrated work uses Herdr session `ipse`, `biz`, or `work`. Before dispatch:

```bash
headroom doctor
herdr --session <session> agent list
```

Headroom must be healthy. Worker order is binding:

1. DeepSeek V4 Flash `xhigh` through OpenCode.
2. The same free DeepSeek model through Cline when OpenCode is unavailable; launch Cline with `--thinking xhigh --compaction agentic --retries 1 --timeout 600`.
3. GPT through Pi when the free routes are unavailable or the brief explicitly requires GPT. Default to GPT-5.6 Luna `Max`; a stronger GPT model requires a one-line justification in the brief.

Do not run OpenCode and Cline for the same deliverable or use another fallback. Default to one worker and one whole, independently verifiable deliverable. Parallelize only disjoint deliverables with satisfied dependencies, separate writable and semantic surfaces, and lower integration cost than serial work.

Every worker starts through `scripts/dispatch_worker.py`. It chooses the first approved route, locks the deliverable against duplicate launches, creates one pane, sends one brief, supervises the worker, closes only that pane, and returns one `accepted|blocked` receipt. Raw `herdr agent start` and `herdr agent prompt` calls are outside the contract.

## Compact bridge

The initial brief must be at most 1,200 characters and contain only:

1. `role=worker; outcome=` one finished result.
2. `write=` exact paths; all other paths are read-only.
3. `non-goals=` exclusions and external-action limits.
4. `accept=` commands or observable checks.
5. `return=accepted|blocked: paths=<...>; checks=<...>; blocker=<...>; then stop`.

Workers do not delegate, narrate progress, write plans, or do discovery that the captain can do read-only. The dispatcher sends one prompt. The inbound bridge is only changed paths, concise evidence, and `accepted|blocked`.

## Hard budgets

Defaults per worker:

- 10 minutes wall time; 20 only when the brief states why.
- 40 Headroom requests; 80 only for explicitly substantial work.
- one prompt; no correction or unchanged replay.
- a token ceiling stated before dispatch when the runtime exposes usage.

The dispatcher starts `scripts/watch_worker.py` automatically. It interrupts at the wall or idle limit and, for Headroom-backed routes, at request or token ceilings. Cline's hosted free route exposes only its hard time/retry bounds. `audit_session.py` remains the post-run tool-call check when a JSONL transcript exists. Stop earlier after three repeated failures; never resend the brief.

## Captain loop

1. Select mode and session; run the runtime gate.
2. Define the fewest whole deliverables and the compact bridge.
3. Write the five-line brief to a file and run `dispatch_worker.py` once.
4. Verify its receipt read-only. Accept, discard with a reason, or report blocked.
5. Report outcome and checks, not orchestration ceremony.

For a suspect legacy transcript, run `scripts/audit_session.py <session.jsonl>`. It reports prompts, prompt bytes, turns, tool calls, time, and tokens and exits nonzero on default budget violations.

Never self-execute while still in orchestrate mode. If remediation is exhausted, report blocked or recommend DIY and wait for Hung to switch.

## References

- Commands: [cli-cheatsheet.md](references/cli-cheatsheet.md)
- Kernel: `backups/orchestration/AGENTS.md`
