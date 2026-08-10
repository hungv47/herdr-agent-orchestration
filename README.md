![One captain, any worker](assets/cover.png)

# One captain, bounded workers

A portable Herdr contract for using a strong user-facing captain with cheaper or free coding workers—without orchestration loops consuming more tokens than the work.

## The contract

Before side effects, the captain recommends `DIY` or `orchestrate` and asks once unless the user already chose.

- **DIY:** execute and verify directly. Prefer this for small, cohesive, or borderline work.
- **Orchestrate:** the captain performs no task writes. It sends one whole deliverable through the guarded dispatcher, verifies once, and reports.

Orchestration must save more execution cost than dispatch, supervision, and verification add. One worker is the default; worker count is not progress.

## Enforced budgets

The policy is backed by executable limits:

| surface | default ceiling | substantial ceiling |
|---|---:|---:|
| Hermes captain | 8 model iterations per user turn | none |
| worker wall time | 5 minutes | 10 minutes |
| worker idle time | 90 seconds | 2 minutes |
| worker model requests | 5 | 8 |
| worker uncached input | 50k | 90k |
| worker output | 5k | 10k |
| worker prompts | 1 | 1 |

Hermes automatic memory/skill-review forks are disabled. The installer guards raw Herdr mutations and configures Headroom's shared $5 daily, 60k TPM, 10 RPM, and three-connection backstop. Request logs separate uncached input from replayed cached context, so a large cached prefix is reported but not mistaken for new work.

A blocked receipt ends the attempt. The captain does not repair infrastructure, re-prompt, replay, or silently fall back during that run.

## Worker routes

1. DeepSeek V4 Flash `xhigh` through OpenCode.
2. The same free model through bounded Cline when OpenCode is unavailable or a disjoint second free lane is justified.
3. GPT-5.6 Luna `Max` through Pi only when the deliverable explicitly requires GPT.

Each harness lane has a process lock. Parallel workers may use separate lanes only when their dependencies, writable paths, semantic surfaces, and runtime resources are disjoint.

## Five-line bridge

Every worker receives at most 1,200 characters:

```text
role=worker; outcome=<one finished result>
write=<exact paths; everything else read-only>
non-goals=<exclusions and external-action limits>
accept=<commands or observable checks>
return=accepted|blocked: paths=<paths>; checks=<checks>; blocker=<blocker>; then stop
```

Workers do not delegate, narrate progress, write plans, or perform discovery the captain can do read-only.

## Guarded dispatch

```bash
python3 skills/ops-herdr-orchestration/scripts/dispatch_worker.py \
  --session biz \
  --name useful-unit \
  --cwd /path/to/repo \
  --brief-file /tmp/brief.txt
```

For explicit GPT work:

```bash
python3 skills/ops-herdr-orchestration/scripts/dispatch_worker.py \
  --session biz --name hard-unit --cwd /path/to/repo --brief-file /tmp/brief.txt \
  --gpt-reason 'requires stronger repository-wide reasoning'
```

For a disjoint Cline lane:

```bash
python3 skills/ops-herdr-orchestration/scripts/dispatch_worker.py \
  --session biz --name independent-unit --cwd /path/to/repo --brief-file /tmp/brief.txt \
  --route cline --route-reason 'disjoint paths and checks'
```

The dispatcher owns pane creation, one prompt, supervision, receipt parsing, and cleanup. Raw worker start or prompt commands are outside the contract.

## Install

Prerequisites: Bash, Python 3, Herdr, Headroom, and at least one approved worker CLI.

```bash
bash scripts/install.sh                    # preview
bash scripts/install.sh --apply            # policies, skill, Herdr guard, Hermes ceilings
sh scripts/install-headroom.sh             # compression + shared spend/rate limits
bash scripts/verify.sh
bash scripts/verify.sh --installed
```

The installer links the shared policy and skill into supported agent homes. When Hermes is installed, it sets `agent.max_turns=8`, `memory.nudge_interval=0`, `skills.creation_nudge_interval=0`, and `code_execution.max_tool_calls=12`.

## Audits

Audits are diagnostic, not a dispatch ceremony:

```bash
python3 skills/ops-herdr-orchestration/scripts/audit_session.py worker.jsonl
python3 skills/ops-herdr-orchestration/scripts/audit_hermes_session.py \
  ~/.hermes/logs/agent.log --session SESSION_ID --orchestrated
```

Both exit nonzero on waste. Repository verification includes regression coverage for cached-token accounting, lane isolation, one-prompt bridges, captain loops, and captain writes.

## Official links

- [Herdr](https://github.com/herdrdev/herdr)
- [Headroom](https://github.com/headroomlabs-ai/headroom)
- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
- [Pi](https://github.com/earendil-works/pi)
