# Orchestration efficiency eval

Run this eval before worker dispatch and after captain verification. It measures useful outcomes, safe parallelism, prompt loops, and token budgets without storing prompt content.

## Trace

Write one temporary JSON file using schema `herdr-orchestration-run/v1`. Each worker record contains:

- `id`, `deliverable`, and `delegation_reason`;
- `writable_paths`, `semantic_surfaces`, and `runtime_resources`; use empty lists when none;
- `acceptance`, `stop_condition`, and `return_format`—the compact outbound bridge;
- `parallel_group` or `null`, plus `depends_on`;
- `prompt_count`, `correction_count`, and `same_blocker_repeated`;
- `outcome`: `pending`, `accepted`, `discarded`, or `blocked`;
- `result_used`, `evidence`, and `closure_reason`—the compact inbound bridge;
- `token_budget` and `tokens_used`; use `null` for both when trustworthy usage is unavailable; and
- for duplicate read-only review scope, `review_justification`.

Allowed `delegation_reason` values are `parallel-independent`, `specialization`, `duration`, `risk`, and `independent-review`.

Do not include prompt text, private source content, credentials, personal paths, worker transcripts, or full terminal output.

Start from one worker and add workers only when the parallel gate passes:

```json
{
  "schema": "herdr-orchestration-run/v1",
  "objective": "<user-visible outcome>",
  "workers": [{
    "id": "<worker>",
    "deliverable": "<finished, independently verifiable output>",
    "delegation_reason": "specialization",
    "writable_paths": ["<exact/path>"],
    "semantic_surfaces": ["<contract-or-component>"],
    "runtime_resources": [],
    "acceptance": ["<command or observable check>"],
    "stop_condition": "<stop without guessing when...>",
    "return_format": "changed artifact references and concise check evidence",
    "parallel_group": null,
    "depends_on": [],
    "prompt_count": 0,
    "correction_count": 0,
    "same_blocker_repeated": false,
    "outcome": "pending",
    "result_used": false,
    "evidence": [],
    "closure_reason": null,
    "token_budget": null,
    "tokens_used": null
  }]
}
```

## Commands

From the repository root:

```bash
EVAL=skills/ops-herdr-orchestration/scripts/eval_run.py
python3 "$EVAL" --phase preflight "$TRACE"
python3 "$EVAL" --phase final "$TRACE"
```

Preflight fails incomplete bridges, duplicate worker IDs, unknown or self-dependencies, dependent or overlapping parallel work, unjustified duplicate scope, unsafe paths, and malformed budgets. Final also fails more than two prompts, more than one correction, a repeated blocker, unverified or unused accepted output, unexplained blocked or discarded output, pending work, and recorded token use above budget.

The result reports worker count, accepted-output ratio, prompts, corrections, token-usage coverage, and violations. A failing eval requires a smaller plan, a revised brief, or an explicit blocked report; do not waive it by replaying the same task.
