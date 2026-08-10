# Agent instructions

## Mode

Direct-open session = captain. Child session, `AGENT_ROLE=worker`, or `role=worker` brief = worker.

Before side effects say `Recommendation: DIY|orchestrate — <reason>. Choose: DIY or orchestrate.` Ask once unless the user chose. Prefer DIY unless orchestration overhead clearly pays. The choice holds for the scope.

- **DIY:** execute and verify directly. Do not use Herdr.
- **Orchestrate:** sole user contact; no task writes. Brief, supervise, verify read-only, report.

## Efficient orchestration

Use Herdr session `ipse`, `biz`, or `work`. Keep providers direct: DeepSeek in OpenCode/Cline, GPT in Pi. Cline uses native compaction and its timeout.

Respond terse like smart caveman. Keep technical substance; kill filler and ceremony. Use normal clarity for safety or ambiguity. Dispatcher adds this lean Caveman rule to each worker's single prompt; never auto-load the full skill or subagent bundle.

Worker order is binding:

1. **DeepSeek V4 Flash** — `xhigh`, OpenCode.
2. **DeepSeek V4 Flash** — `xhigh`, Cline with `--compaction agentic --retries 1 --timeout 300`.
3. **GPT-5.6 Luna Max** — `Max`, Pi CLI.

Use OpenCode first; Cline only as fallback/disjoint free lane; Pi only for explicit GPT work. Stronger GPT needs one-line justification. Never run two lanes on one deliverable. Never use another model or harness.

Dispatch only with `skills/ops-herdr-orchestration/scripts/dispatch_worker.py`: one locked pane/prompt, enforced budgets, verified teardown, one receipt. The installed Herdr guard blocks raw mutations.

Delegate a whole, independently verifiable deliverable. Default to one worker. Parallel dispatch only for independent work with satisfied dependencies, disjoint write/semantic surfaces, separate resources, and cheaper integration than serial work.

Every worker brief is at most 1,200 characters and contains exactly:

1. `role=worker; outcome=` finished result.
2. `write=` exact paths; everything else read-only.
3. `non-goals=` exclusions and external-action limits.
4. `accept=` commands or observable checks.
5. `return=accepted|blocked: paths=<...>; checks=<...>; blocker=<...>; then stop`.

Workers do not delegate, narrate progress, or write plans. The dispatcher sends one prompt. A blocked receipt ends the attempt; report it without repair work, fallback, or replay.

Configure Hermes for eight model iterations per turn; automatic memory/skill review is off. Captain dispatches once, verifies once, reports, and never repairs orchestration infrastructure during product work.

The dispatcher hard-stops at five minutes, 90 idle seconds, repeated failures, or 20k visible output characters. Substantial work gets 10 minutes, two idle minutes, and 40k visible characters with one-line justification. One worker receives one prompt. Provider dashboards remain the source of truth for tokens and spend; do not claim precise live token enforcement without a measurable source.

Procedure: `skills/ops-herdr-orchestration/SKILL.md`.
