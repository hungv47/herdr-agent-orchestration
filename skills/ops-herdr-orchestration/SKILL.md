---
name: ops-herdr-orchestration
description: "Use when choosing DIY vs Herdr, briefing or supervising Herdr workers, preventing retry loops, or auditing orchestration token efficiency."
version: 6.1.0
license: MIT
platforms: [macos, linux]
---

# Herdr orchestration

Binding policy: `AGENTS.md`.

## Choose the cheaper execution path

- DIY for small, cohesive, borderline, or read-mostly work.
- Orchestrate only when independent workstreams, specialization, risk, or duration repay dispatch and verification overhead.
- Keep the selected mode for the same scope. A stalled worker never changes it.
- In orchestrate mode the captain stays the sole user contact and performs no task writes.

## Runtime gate

```bash
headroom doctor
herdr --session <ipse|biz|work> agent list
```

Headroom must be healthy. Worker order is binding:

1. DeepSeek V4 Flash `xhigh` through OpenCode.
2. The same free DeepSeek model through Cline when OpenCode is unavailable; launch Cline with `--thinking xhigh --compaction agentic --retries 1 --timeout 600`.
3. GPT through Pi when the free routes are unavailable or the brief explicitly requires GPT. Default to GPT-5.6 Luna `Max`; a stronger GPT model requires a one-line justification in the brief.

Do not run OpenCode and Cline for the same deliverable or use another fallback. Default to one worker and one whole, independently verifiable deliverable. Parallelize only disjoint deliverables with satisfied dependencies, separate writable and semantic surfaces, and lower integration cost than serial work.

## Compact bridge

The initial brief must be at most 1,200 characters:

1. `role=worker; outcome=` one finished result.
2. `write=` exact paths; all other paths are read-only.
3. `non-goals=` exclusions and external-action limits.
4. `accept=` commands or observable checks.
5. `return=` changed paths, check results, blocker; then stop.

Workers do not delegate, narrate progress, write plans, or do discovery the captain can do read-only. Give one initial prompt and at most one corrective prompt.

## Hard budgets

- 10 minutes wall time; 20 only when the brief states why.
- 40 tool calls; 80 only for explicitly substantial work.
- one correction; no unchanged replay.
- a token ceiling stated before dispatch when usage is exposed.
- five minutes without material progress is an interrupt.

Run `scripts/watch_worker.py --session <session> --agent <name>` after dispatch. It interrupts at the wall or idle limit without closing the pane. Stop earlier after three repeats of the same failing call, blocker, or acceptance failure. Never resend after a wait timeout.

## Captain loop

1. Select mode and session; run the runtime gate.
2. Define the fewest whole deliverables and compact bridge.
3. Start uniquely named workers in unfocused panes.
4. Supervise with `get`, `read`, `wait`, and the watcher. Correct once at most.
5. Verify returned evidence read-only. Accept, discard with a reason, or report blocked.
6. Close only panes created here. Report outcome and checks, not ceremony.

Audit suspect Pi-style JSONL with `scripts/audit_session.py <session.jsonl>`.

Never self-execute while still in orchestrate mode. If remediation is exhausted, report blocked or recommend DIY and wait for the user to switch.
