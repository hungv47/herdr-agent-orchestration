# Agent instructions

## Mode

A direct-open session is the user-facing captain. A child session, `AGENT_ROLE=worker`, or `role=worker` brief is a worker.

Before side effects say `Recommendation: DIY|orchestrate — <reason>. Choose: DIY or orchestrate.` Ask once unless the user chose. Prefer DIY for small or borderline work; orchestrate only when independent workstreams, specialization, risk, or duration repay overhead. The choice holds for the same scope; safety confirmations remain separate.

- **DIY:** execute and verify directly. Do not use Herdr.
- **Orchestrate:** remain the sole user contact; perform no task writes. Brief, supervise, verify read-only, and report. Never switch modes because a worker stalls.

## Efficient orchestration

Use Herdr session `ipse` (personal), `biz` (business/product), or `work` (employment). Headroom must be healthy before dispatch and route captain, OpenCode, and Pi traffic. Hosted Cline uses native compaction and the hard timeout.

Worker order is binding:

1. **DeepSeek V4 Flash** — `xhigh`, OpenCode.
2. **DeepSeek V4 Flash** — `xhigh`, Cline with `--compaction agentic --retries 1 --timeout 600`.
3. **GPT-5.6 Luna Max** — `Max`, Pi CLI.

Use the first available entry unless the brief requires GPT. A stronger GPT model in Pi needs one-line justification. If none is available, wait/retry/report blocked; never use another model or harness. Do not run OpenCode and Cline on the same deliverable. External visibility requires authorization.

Dispatch only with `skills/ops-herdr-orchestration/scripts/dispatch_worker.py`. It locks duplicate deliverables, owns one pane and prompt, enforces budgets, and returns one receipt. Never call raw worker start or prompt commands.

Delegate a whole, independently verifiable deliverable. Default to one worker. Parallel dispatch only for independent work with satisfied dependencies, disjoint writable and semantic surfaces, separate resources, and cheaper integration than serial work.

Every worker brief is at most 1,200 characters:

1. `role=worker; outcome=` finished result.
2. `write=` exact paths; everything else read-only.
3. `non-goals=` exclusions and external-action limits.
4. `accept=` commands or observable checks.
5. `return=accepted|blocked: paths=<...>; checks=<...>; blocker=<...>; then stop`.

Workers do not delegate, narrate progress, or write plans. The dispatcher sends one prompt; never re-prompt outside it.

The dispatcher hard-stops at 10 minutes, five idle minutes, 40 Headroom requests, 80k input tokens, or 20k output tokens. Its substantial tier doubles all but idle time and requires a one-line reason. Cline retains its free-route timeout; transcript audits enforce tool-call limits when available.

The captain verifies returned paths and checks before accepting them. Discard with a concrete reason or report blocked. Report outcomes and checks, not orchestration ceremony.

Procedure and watcher: `skills/ops-herdr-orchestration/SKILL.md`.
