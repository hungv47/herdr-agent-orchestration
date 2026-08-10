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
2. **DeepSeek V4 Flash** — `xhigh`, Cline with `--compaction agentic --retries 1 --timeout 600`.
3. **GPT-5.6 Luna Max** — `Max`, Pi CLI.

Use OpenCode first; Cline only as fallback or a disjoint second free lane; Pi only for explicit GPT work. Stronger GPT needs one-line justification. Never run two lanes on one deliverable. Never use another model or harness.

Dispatch only with `skills/ops-herdr-orchestration/scripts/dispatch_worker.py`. It locks duplicate deliverables and each harness lane, owns one pane and prompt, enforces budgets, and returns one receipt. Never call raw worker start or prompt commands.

Delegate a whole, independently verifiable deliverable. Default to one worker. Parallel dispatch only for independent work with satisfied dependencies, disjoint writable and semantic surfaces, separate resources, and cheaper integration than serial work.

Every worker brief is at most 1,200 characters and contains exactly:

1. `role=worker; outcome=` finished result.
2. `write=` exact paths; everything else read-only.
3. `non-goals=` exclusions and external-action limits.
4. `accept=` commands or observable checks.
5. `return=accepted|blocked: paths=<...>; checks=<...>; blocker=<...>; then stop`.

Workers do not delegate, narrate progress, or write plans. The dispatcher sends one prompt. A blocked receipt ends the attempt; report it without repair work, fallback, or replay.

Configure Hermes for eight model iterations per user turn with automatic memory/skill review disabled. The captain makes one dispatch call, waits for its receipt, verifies once, and reports. It never repairs orchestration infrastructure during a product run.

The dispatcher hard-stops at eight minutes, two idle minutes, eight model requests, 80k uncached input tokens, or 8k output. Substantial work gets 15 minutes, 12 requests, 140k uncached input, and 16k output with one-line justification. Cached context is reported, not charged as new work.

Procedure: `skills/ops-herdr-orchestration/SKILL.md`.
