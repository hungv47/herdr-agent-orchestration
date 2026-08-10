# Agent instructions

## Mode

A direct-open session is the user-facing captain. A child session, `AGENT_ROLE=worker`, or `role=worker` brief is a worker.

Before side effects say `Recommendation: DIY|orchestrate — <reason>. Choose: DIY or orchestrate.` Ask once unless the user chose. Prefer DIY unless orchestration overhead clearly pays. The choice holds for the scope.

- **DIY:** execute and verify directly. Do not use Herdr.
- **Orchestrate:** remain the sole user contact; perform no task writes. Brief, supervise, verify read-only, and report.

## Efficient orchestration

Use Herdr session `ipse`, `biz`, or `work`. Headroom must be healthy and route captain, OpenCode, and Pi traffic. Cline uses native compaction and its timeout.

Worker order is binding:

1. **DeepSeek V4 Flash** — `xhigh`, OpenCode.
2. **DeepSeek V4 Flash** — `xhigh`, Cline with `--compaction agentic --retries 1 --timeout 300`.
3. **GPT-5.6 Luna Max** — `Max`, Pi CLI.

Use OpenCode first; Cline only as fallback or a disjoint second free lane; Pi only for explicit GPT work. Stronger GPT needs one-line justification. Never run two lanes on one deliverable. Never use another model or harness.

Dispatch only with `skills/ops-herdr-orchestration/scripts/dispatch_worker.py`. It locks duplicate deliverables and each harness lane, owns one pane and prompt, enforces budgets, verifies teardown, and returns one receipt. The installed Herdr guard mechanically blocks raw mutations.

Delegate a whole, independently verifiable deliverable. Default to one worker. Parallel dispatch only for independent work with satisfied dependencies, disjoint writable and semantic surfaces, separate resources, and cheaper integration than serial work.

Every worker brief is at most 1,200 characters and contains exactly:

1. `role=worker; outcome=` finished result.
2. `write=` exact paths; everything else read-only.
3. `non-goals=` exclusions and external-action limits.
4. `accept=` commands or observable checks.
5. `return=accepted|blocked: paths=<...>; checks=<...>; blocker=<...>; then stop`.

Workers do not delegate, narrate progress, or write plans. The dispatcher sends one prompt. A blocked receipt ends the attempt; report it without repair work, fallback, or replay.

Configure Hermes for eight model iterations per user turn with automatic memory/skill review disabled. The captain makes one dispatch call, waits for its receipt, verifies once, and reports. It never repairs orchestration infrastructure during a product run.

The dispatcher hard-stops at five minutes, 90 idle seconds, five model requests, 50k uncached input tokens, or 5k output. Substantial work gets 10 minutes, eight requests, 90k uncached input, and 10k output with one-line justification. Headroom also enforces a $5 daily budget, 60k TPM, 10 RPM, and three concurrent connections unless the operator explicitly overrides them. Cached context is reported, not charged as new work.

Procedure: `skills/ops-herdr-orchestration/SKILL.md`.
