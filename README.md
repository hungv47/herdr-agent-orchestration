# Just use Firstmate bro
https://github.com/kunchenguid/firstmate

# Ignore this (this was a nice experiment btw)
![One captain, any worker](assets/cover.png)

# Herdr-first captain

A Herdr-first captain/worker workflow for Hermes, Codex, Grok, OpenCode, Cline, Buzz, and other coding agents—without spending more tokens on orchestration than on the work.

## What this repository owns

- the canonical global [captain contract](AGENTS.md);
- the compact worker bridge and loop stops;
- Headroom routing policy and measured adoption gates;
- verification that retired private dispatchers and ceremony stay gone.

Official [Herdr](https://github.com/herdrdev/herdr) owns panes, agent discovery, lifecycle state, waiting, and timeouts. This repository adds behavior, not a second dispatcher, watcher, proxy manager, or Herdr wrapper.

## Operating model

1. The user-facing session is captain; Herdr-started sessions are workers.
2. Direct execution handles one small cohesive deliverable. Herdr handles long, independent, specialized, or parallel work where coordination pays.
3. One complete deliverable goes to one worker by default. The captain sends one brief, waits on state, verifies once, and allows one exact correction.
4. Repeated failure, no progress, or a worker producing no artifact ends the attempt. Nothing is automatically replayed through another model or CLI.
5. Cheap or free capable workers go first. Stronger paid models require task or acceptance evidence.

The always-loaded [AGENTS.md](AGENTS.md) is intentionally short. CLI mechanics remain version-authoritative in the official skill printed by `herdr --skill`.

## Worker bridge

```text
role=worker; outcome=<finished result>
scope=<writable paths; everything else read-only>
constraints=<only material exclusions or external-action limits>
accept=<commands or observable checks>
return=done|blocked; paths=<paths>; checks=<checks>; blocker=<reason>; stop
```

Aim below 800 characters. Brief length never blocks a launch or removes safety and acceptance criteria.

## Headroom

Headroom is the data plane; Herdr is the control plane. Start supported clients through their exact live `headroom wrap` command; the wrapper starts the proxy. Do not add a standalone doctor check to every session. Use `headroom doctor` only after a wrapper fails before useful work or during an evaluation, then fall back direct once without replaying work.

The installed CLI is the compatibility authority:

```bash
headroom wrap --help
```

Codex, Grok, OpenCode, and Cline currently expose wrappers or setup commands. Headroom exposes an `omp` route for Oh My Pi, but that is not the installed `pi` command. Hermes, Buzz, and `pi` therefore run direct unless the live wrapper list later names them exactly. A Herdr worker is routed only when its configured launch command actually uses Headroom.

Use [the five-case evaluation](evals/README.md) before making a new route persistent. Adoption requires identical acceptance, measured input savings, bounded latency/output regression, no prompt retries, no persistent config damage, and a working direct bypass.

## Install locally

In IPSE, `backups/orchestration/AGENTS.md` is the private canonical source and this repository is its byte-identical public mirror. The sync script links that source into Codex, Claude, Grok, Gemini, OpenCode, Pi, Cline, Copilot, Hermes, and other detected homes; Buzz receives the same contract inside its managed workspace file.

## Verify

```bash
bash scripts/verify.sh
python3 evals/score_trial.py path/to/results.json
```

The scorer proves its gates work; real provider receipts and completed acceptance checks prove savings.

## References

- [Herdr](https://github.com/herdrdev/herdr) — agent control plane
- [Firstmate](https://github.com/kunchenguid/firstmate) — event-driven liaison/crew ideas
- [Headroom](https://github.com/headroomlabs-ai/headroom) — context optimization
