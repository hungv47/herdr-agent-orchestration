---
name: ops-herdr-orchestration
description: "Use when choosing DIY vs Herdr, briefing or supervising Herdr workers, preventing retry loops, or auditing orchestration token efficiency."
version: 1.0.0
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [herdr, orchestration, multi-cli, manager-worker, token-efficiency]
---

# Herdr orchestration

Binding policy: the repository root `AGENTS.md`.

- Use the strongest available reasoning model for captain judgment and cheaper or free models for bounded execution.
- Prefer DIY for small or borderline work. Orchestration must save more execution cost than it adds in coordination.
- In DIY mode, execute and verify directly.
- In orchestrate mode, the captain performs no task writes and remains the sole user contact.

## Dispatch gate

Translate the request into the fewest whole, independently verifiable deliverables. Default to one worker. Do not delegate discovery, planning fragments, status checks, or summaries the captain can do read-only.

Parallelize only when every candidate has satisfied dependencies, distinct writable and semantic surfaces, no shared runtime singleton, and cheaper integration than serial execution. Use the smallest sufficient wave. OpenCode and Cline are two DeepSeek lanes, not an automatic duplicate pair. Duplicate scope is reserved for justified read-only independent review.

Before dispatch, read [efficiency-eval.md](references/efficiency-eval.md), create its compact trace under the system temporary directory, and run the preflight. The trace is orchestration control data, not repository output.

## Verifiable bridge

Every worker gets one outbound bridge and returns one inbound bridge.

Outbound:

1. one stable worker identity;
2. one finished outcome;
3. exact writable paths;
4. non-goals and external-action authority;
5. acceptance commands or observables;
6. required evidence and return format; and
7. a stop condition that prevents guessing or replay loops.

Inbound:

1. the same worker identity;
2. changed artifact references;
3. concise acceptance evidence; and
4. an accepted, discarded, or blocked outcome.

The captain independently verifies the inbound evidence before using the result. Output that does not feed the delivered result closes as discarded with a concrete reason.

## Captain loop

1. Evaluate and obtain the mode.
2. DIY: execute, verify, report, and stop here.
3. Orchestrate: choose the approved Herdr session and worker pool.
4. Prove the orchestration value gate, define the fewest whole deliverables, and make the efficiency preflight pass.
5. Spawn uniquely named workers and confirm each outbound bridge reached one worker.
6. Supervise with read/wait operations. A timeout is not evidence of a stopped worker, so never resend the brief merely because a wait timed out.
7. Give at most one corrective prompt. Stop on the same repeated blocker or a second acceptance failure. Switch workers only for a capability-specific blocker and revise the brief.
8. Verify every inbound bridge read-only, update the trace, and make the final eval pass.
9. Report accepted and discarded outputs, checks, prompts per worker, and tokens when exposed. Close only resources you created.

## Cost rules

- Strong captain, low-cost worker is the intended asymmetry.
- More workers are not more progress.
- The hard prompt budget is one initial brief plus one correction.
- When trustworthy token usage is exposed, record a per-worker budget and actual use.
- When usage is unavailable, prompt count is the required cost proxy.
- Never waive a failing eval by rewording and replaying the same task.

## Session map

- `ipse`: personal work
- `biz`: business and product work
- `work`: current-employment work

## References

- Policy: repository root `AGENTS.md`
- Evaluator: `scripts/eval_run.py`
- Trace contract: [efficiency-eval.md](references/efficiency-eval.md)
