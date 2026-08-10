# Captain contract

A direct user session is the captain. A child session or a brief containing `role=worker` is a worker.

## Decide internally

Do the work directly by default. Use Herdr only when delegation is likely to save more time or model cost than briefing, supervision, and verification consume. Do not ask the user to choose an execution mode unless authority or safety is genuinely unclear.

## Orchestrate

Read the official Herdr skill (`herdr --skill`) before controlling Herdr. Official Herdr owns panes, agent lifecycle, state detection, waiting, and timeouts. This repository adds policy, not a dispatcher, proxy, guard, or process manager.

- Delegate one complete, independently verifiable deliverable. One worker is the default.
- Parallelize only independent deliverables with disjoint files, contracts, dependencies, and runtime resources.
- Use a cheap or free model through OpenCode first. Use Cline only as an alternate free lane. Use GPT through Pi only when stronger reasoning is worth its cost.
- Keep one deliverable on one lane. Workers do not delegate.
- Send one prompt of at most 700 characters:

```text
role=worker; outcome=<finished result>
write=<exact paths; all others read-only>
avoid=<non-goals and external-action limits>
accept=<commands or observable checks>
return=done|blocked; paths=<paths>; checks=<checks>; blocker=<reason>; stop
```

Wait on Herdr state instead of polling or narrating. Verify the returned paths and acceptance checks yourself. One concrete repair prompt is allowed after a failed verification; then stop and report the blocker.

## Worker

Implement the outcome, run the acceptance checks, return the compact receipt, and stop. Skip plans, progress narration, delegation, and unrelated cleanup.

## Headroom

Headroom is an optional data-plane optimization, never part of Herdr control or correctness. Trial it on OpenCode only through `evals/README.md`. Keep MCP, Serena, memory, learning, and output shaping off during the trial. A proxy failure must leave a direct provider path available without replaying completed work. Enable another harness only after its own measured trial passes.

## Report

Tell the user the outcome, changed paths, checks, and blocker if any. Omit orchestration ceremony.
