# Headroom trial

This is an adoption gate, not a benchmark theater loop. Use five worthwhile tasks you would have run anyway. Do not create filler tasks merely to complete the trial.

## Boundaries

- Baseline: direct OpenCode with the same model and starting commit.
- Candidate: `headroom wrap opencode --no-mcp --no-serena`.
- One prompt, zero retries, identical task brief and acceptance command.
- Keep Headroom memory, learning, MCP, Serena, code graph, and output shaping off.
- Use isolated copies or worktrees so the two runs cannot share edits.
- Record tokens from provider or harness receipts. Headroom estimates alone are supporting data, not the source of truth.

## Record each run

Copy `example-input.json` and add five real run objects. For each run record:

- the shared model, starting commit, task-brief digest, acceptance command, and command digest;
- both exit codes and receipt digests;
- uncached input tokens, output tokens, and wall seconds;
- worker prompt and retry counts;
- the metric source: `provider_receipt` or `harness_receipt`;
- a hash of persistent agent configuration before and after the candidate.

Hash only the configuration files relevant to the candidate. Keep the same ordered file list before and after. Example:

```bash
shasum -a 256 ~/.config/opencode/opencode.jsonc ~/.codex/config.toml
```

Use lowercase SHA-256 digests for the task brief, acceptance command, configuration snapshot, provider/harness receipts, and failure-drill receipts. Keep the underlying receipts locally so a passing JSON remains auditable.

## Failure drills

Run these once outside a product task and record the top-level booleans plus SHA-256 digests of their transcripts:

1. Start two wrapped OpenCode sessions. Exit the session that started the proxy. Confirm the second session remains usable.
2. Stop the proxy. Confirm plain OpenCode can start and use its direct provider without repairing persistent config or replaying completed work.

## Score

```bash
python3 evals/score_trial.py results.json
```

Exit `0` means the OpenCode trial passed every gate, including no more than 10% output-token or wall-time regression. Exit `1` means keep Headroom optional and direct. Exit `2` means the evidence file is invalid.

Passing OpenCode approves only that route. Evaluate every additional harness separately.
