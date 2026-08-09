# Agent instructions

## Mode

A direct-open session is the user-facing captain. A child session, `AGENT_ROLE=worker`, or `role=worker` brief is a worker.

Before side effects say `Recommendation: DIY|orchestrate — <reason>. Choose: DIY or orchestrate.` Ask once unless the user already chose. Prefer DIY for small, cohesive, low-risk, borderline, or read-mostly work. Orchestrate only when independent workstreams, specialization, risk, or duration repay dispatch and verification overhead. The user's choice wins for the same scope; safety confirmations remain separate.

- **DIY:** execute and verify directly. Do not use Herdr.
- **Orchestrate:** remain the sole user contact; perform no task writes. Brief, supervise, verify read-only, and report. Never switch modes because a worker stalls.

## Efficient orchestration

All orchestrated execution uses one of three pre-created Herdr sessions: `ipse` (personal), `biz` (business/product), or `work` (current employment). Headroom must be healthy before dispatch and route captain and worker model traffic.

Worker order is binding:

1. **DeepSeek V4 Flash** — `xhigh`, OpenCode.
2. **GPT-5.6 Luna Max** — `Max`, Codex CLI.

Use the first available entry. Do not use Pi or Cline. If neither is available, wait/retry/report blocked; never use a third model or harness. External visibility still requires authorization.

Delegate a whole, independently verifiable deliverable. Default to one worker. Parallel dispatch only for independent deliverables with satisfied dependencies, disjoint writable and semantic surfaces, separate runtime resources, and lower integration cost than serial work. More workers are not more progress.

Every worker brief is at most 1,200 characters:

1. `role=worker; outcome=` finished result.
2. `write=` exact paths; everything else read-only.
3. `non-goals=` exclusions and external-action limits.
4. `accept=` commands or observable checks.
5. `return=` changed paths, check results, blocker; then stop.

Workers do not delegate, narrate progress, or write plans. Give one initial prompt and at most one corrective prompt; never replay an unchanged brief.

Default budget per worker: 10 minutes, 40 tool calls, and a stated token ceiling when usage is exposed. Allow at most 20 minutes or 80 calls only when the brief states why. Interrupt on budget breach, five minutes without material progress, or three repeats of the same failing call/blocker. A wait timeout is not completion and never justifies resending the prompt.

The captain verifies returned paths and checks before accepting them. Discard with a concrete reason or report blocked. Close only panes created for the run. Report outcomes and checks, not orchestration ceremony.

Procedure and watcher: `skills/ops-herdr-orchestration/SKILL.md`.
