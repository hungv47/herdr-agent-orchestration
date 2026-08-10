![One captain, any worker](assets/cover.png)

# One captain, worthwhile workers

A portable Herdr policy for short, verifiable, token-efficient agent sessions.

The default is simple: DIY small work. When orchestration earns its overhead, use one bounded worker, one concise prompt, and hard time/request/token limits. [Headroom](https://github.com/headroomlabs-ai/headroom) compresses captain traffic plus supported worker transports.

## Runtime

```text
User ↔ captain ↔ Headroom
                 ├─ DIY: captain executes
                 └─ Herdr: one bounded worker by default
                    ├─ OpenCode → DeepSeek V4 Flash (free, preferred)
                    ├─ Cline → DeepSeek V4 Flash (free fallback)
                    └─ Pi → GPT-5.6 Luna (or justified stronger GPT)
```

OpenCode and Pi route through Headroom. Cline's hosted free provider does not expose a compatible local proxy route, so its fallback uses Cline's native agentic compaction, one retry, and a hard 600-second timeout.

## Hard contract

- DIY for small, cohesive, borderline, or read-mostly work.
- Orchestrate only when its savings exceed dispatch and verification cost.
- Default to one worker and one whole, independently verifiable deliverable.
- Parallelize only independent, disjoint work with cheaper integration than serial work.
- Briefs: maximum 1,200 characters; outcome, exact writes, non-goals, acceptance, and an exact `paths=; checks=; blocker=` receipt.
- Per worker: 10 minutes, one prompt, 40 Headroom requests, and fixed input/output ceilings.
- Interrupt after five idle minutes, three repeated failures, or any budget breach.
- Workers do not delegate, narrate progress, or write plans.
- All workers launch through one guarded dispatcher; raw launch and prompt commands are outside the contract.

Worker order:

1. DeepSeek V4 Flash `xhigh` through OpenCode.
2. DeepSeek V4 Flash `xhigh` through bounded Cline when OpenCode is unavailable.
3. GPT-5.6 Luna `Max` through Pi when free routes are unavailable or GPT is justified.

Use only Herdr sessions `ipse`, `biz`, and `work`.

## Install

Prerequisites: Bash, Python 3, `uv`, Herdr, Hermes, OpenCode, Cline, and Pi.

```bash
# Preview policy links, then apply.
bash scripts/install.sh
bash scripts/install.sh --apply

# Install Headroom 0.34.0 and route Hermes/Pi/OpenCode.
sh scripts/install-headroom.sh

bash scripts/verify.sh
bash scripts/verify.sh --installed
```

The policy installer also injects a marked policy fragment into an existing Buzz Nest file without replacing Buzz-managed content. The Headroom installer:

- runs a loopback-only persistent proxy with telemetry off;
- enables code-aware compression and output shaping;
- routes Pi GPT and Hermes through the proxy;
- installs Headroom's packaged OpenCode transport plugin;
- installs the Hermes retrieval tool;
- reduces Hermes prompt/tool noise and enables loop hard stops; and
- preserves one pre-Headroom backup of changed configuration.

Run `sh scripts/install-headroom.sh --check` to detect drift.

## Dispatch and audit

```bash
python3 skills/ops-herdr-orchestration/scripts/dispatch_worker.py \
  --session biz --name useful-unit --cwd /path --brief-file brief.txt

python3 skills/ops-herdr-orchestration/scripts/audit_session.py session.jsonl
```

The dispatcher validates the five-line brief, selects OpenCode → Cline → Pi, refuses duplicate deliverables, owns one pane and prompt, and interrupts at wall, idle, Headroom request, or token ceilings. It closes its pane and returns one `accepted|blocked` receipt. The audit adds transcript-level prompt and tool-call enforcement when JSONL is available.

## Safety

Exact writable paths are mandatory. Everything else is read-only. Workers cannot delegate. External, destructive, irreversible, or security-sensitive actions still require explicit authority. Preserve unrelated user work and keep private content out of public surfaces.

## Official links

- [Headroom](https://github.com/headroomlabs-ai/headroom)
- [Herdr](https://github.com/herdrdev/herdr)
- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
