#!/usr/bin/env python3
"""Evaluate a privacy-preserving Herdr orchestration run trace."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import PurePosixPath
from typing import Any

SCHEMA = "herdr-orchestration-run/v1"
OUTCOMES = {"pending", "accepted", "discarded", "blocked"}
REASONS = {
    "parallel-independent",
    "specialization",
    "duration",
    "risk",
    "independent-review",
}


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def path_parts(value: str) -> tuple[str, ...]:
    return PurePosixPath(value.rstrip("/")).parts


def paths_overlap(left: str, right: str) -> bool:
    a, b = path_parts(left), path_parts(right)
    return a == b or a == b[: len(a)] or b == a[: len(b)]


def evaluate(trace: Any, phase: str) -> dict[str, Any]:
    violations: list[str] = []
    if not isinstance(trace, dict):
        return result(phase, [], ["trace must be a JSON object"])
    if trace.get("schema") != SCHEMA:
        violations.append(f"schema must be {SCHEMA}")
    if not nonempty(trace.get("objective")):
        violations.append("objective must be non-empty")
    workers = trace.get("workers")
    if not isinstance(workers, list) or not workers:
        return result(phase, [], violations + ["workers must be a non-empty list"])

    ids: list[str] = []
    parallel: dict[str, list[dict[str, Any]]] = {}
    deliverables: dict[str, list[dict[str, Any]]] = {}
    for index, worker in enumerate(workers):
        label = f"workers[{index}]"
        if not isinstance(worker, dict):
            violations.append(f"{label} must be an object")
            continue
        worker_id = worker.get("id")
        if not nonempty(worker_id):
            violations.append(f"{label}.id must be non-empty")
            worker_id = label
        elif worker_id in ids:
            violations.append(f"duplicate worker id: {worker_id}")
        ids.append(worker_id)
        prefix = f"worker {worker_id}"

        deliverable = worker.get("deliverable")
        if not nonempty(deliverable) or len(deliverable.strip()) < 20:
            violations.append(f"{prefix}: deliverable must name a whole, verifiable outcome")
        else:
            deliverables.setdefault(deliverable.strip().lower(), []).append(worker)
        if worker.get("delegation_reason") not in REASONS:
            violations.append(f"{prefix}: invalid delegation_reason")
        for field in ("stop_condition", "return_format"):
            if not nonempty(worker.get(field)):
                violations.append(f"{prefix}: {field} must be non-empty")
        acceptance = worker.get("acceptance")
        if not isinstance(acceptance, list) or not acceptance or not all(
            nonempty(item) for item in acceptance
        ):
            violations.append(
                f"{prefix}: outbound bridge acceptance must contain a verifiable check"
            )

        writable = worker.get("writable_paths")
        if not isinstance(writable, list) or not all(nonempty(item) for item in writable):
            violations.append(f"{prefix}: writable_paths must be a string list")
            writable = []
        for path in writable:
            if (
                path in {".", "..", "/", "~"}
                or ".." in PurePosixPath(path).parts
                or any(char in path for char in "*?[]")
            ):
                violations.append(f"{prefix}: writable path is broad or unresolved: {path}")

        for field in ("semantic_surfaces", "runtime_resources"):
            values = worker.get(field)
            if not isinstance(values, list) or not all(nonempty(item) for item in values):
                violations.append(f"{prefix}: {field} must be a string list")

        dependencies = worker.get("depends_on")
        if not isinstance(dependencies, list) or not all(nonempty(item) for item in dependencies):
            violations.append(f"{prefix}: depends_on must be a string list")
        group = worker.get("parallel_group")
        if group is not None and not nonempty(group):
            violations.append(f"{prefix}: parallel_group must be null or non-empty")
        elif nonempty(group):
            parallel.setdefault(group, []).append(worker)

        for field in ("prompt_count", "correction_count"):
            if not integer(worker.get(field)):
                violations.append(f"{prefix}: {field} must be a non-negative integer")
        if not isinstance(worker.get("same_blocker_repeated"), bool):
            violations.append(f"{prefix}: same_blocker_repeated must be boolean")

        budget, used = worker.get("token_budget"), worker.get("tokens_used")
        if (budget is None) != (used is None):
            violations.append(f"{prefix}: token_budget and tokens_used must both be null or integers")
        elif budget is not None:
            if not integer(budget) or budget == 0 or not integer(used):
                violations.append(f"{prefix}: token budget and usage must be positive/non-negative integers")

        outcome = worker.get("outcome")
        if outcome not in OUTCOMES:
            violations.append(f"{prefix}: invalid outcome")
        if not isinstance(worker.get("result_used"), bool):
            violations.append(f"{prefix}: result_used must be boolean")
        evidence = worker.get("evidence")
        if not isinstance(evidence, list) or not all(nonempty(item) for item in evidence):
            violations.append(f"{prefix}: evidence must be a string list")

        if phase == "final":
            prompts, corrections = worker.get("prompt_count"), worker.get("correction_count")
            if integer(prompts) and prompts > 2:
                violations.append(f"{prefix}: prompt loop ({prompts} prompts; maximum is 2)")
            if integer(corrections) and corrections > 1:
                violations.append(f"{prefix}: more than one corrective prompt")
            if integer(prompts) and integer(corrections) and prompts != corrections + 1:
                violations.append(f"{prefix}: prompt_count must equal initial brief plus corrections")
            if worker.get("same_blocker_repeated") is True:
                violations.append(f"{prefix}: same blocker repeated")
            if outcome == "pending":
                violations.append(f"{prefix}: outcome is still pending")
            elif outcome == "accepted":
                if worker.get("result_used") is not True:
                    violations.append(f"{prefix}: accepted inbound bridge was not used")
                if not evidence:
                    violations.append(
                        f"{prefix}: accepted inbound bridge lacks verification evidence"
                    )
            elif outcome in {"discarded", "blocked"} and not nonempty(
                worker.get("closure_reason")
            ):
                violations.append(f"{prefix}: {outcome} output needs a closure_reason")
            if integer(budget) and integer(used) and used > budget:
                violations.append(f"{prefix}: tokens_used exceeds token_budget")

    all_ids = set(ids)
    for worker in workers:
        if not isinstance(worker, dict) or not nonempty(worker.get("id")):
            continue
        for dependency in worker.get("depends_on") or []:
            if dependency == worker["id"]:
                violations.append(f"worker {worker['id']}: depends_on contains itself")
            elif dependency not in all_ids:
                violations.append(f"worker {worker['id']}: unknown dependency {dependency}")

    for group, members in parallel.items():
        if len(members) < 2:
            violations.append(f"parallel group {group}: must contain at least two workers")
            continue
        member_ids = {member.get("id") for member in members}
        for member in members:
            dependencies = member.get("depends_on") or []
            if any(dependency in member_ids for dependency in dependencies):
                violations.append(f"parallel group {group}: contains an internal dependency")
        for index, left in enumerate(members):
            for right in members[index + 1 :]:
                for left_path in left.get("writable_paths") or []:
                    for right_path in right.get("writable_paths") or []:
                        if paths_overlap(left_path, right_path):
                            violations.append(
                                f"parallel group {group}: writable paths overlap "
                                f"({left_path}, {right_path})"
                            )
                read_only_review = all(
                    member.get("delegation_reason") == "independent-review"
                    and not member.get("writable_paths")
                    for member in (left, right)
                )
                if not read_only_review:
                    shared_semantics = set(left.get("semantic_surfaces") or []) & set(
                        right.get("semantic_surfaces") or []
                    )
                    if shared_semantics:
                        violations.append(
                            f"parallel group {group}: semantic surfaces overlap "
                            f"({', '.join(sorted(shared_semantics))})"
                        )
                shared_runtime = set(left.get("runtime_resources") or []) & set(
                    right.get("runtime_resources") or []
                )
                if shared_runtime:
                    violations.append(
                        f"parallel group {group}: runtime resources overlap "
                        f"({', '.join(sorted(shared_runtime))})"
                    )

    for duplicate, members in deliverables.items():
        if len(members) < 2:
            continue
        justified = all(
            member.get("delegation_reason") == "independent-review"
            and not member.get("writable_paths")
            and nonempty(member.get("review_justification"))
            for member in members
        )
        if not justified:
            violations.append(f"duplicate deliverable without justified read-only review: {duplicate}")

    return result(phase, workers, violations)


def result(phase: str, workers: list[Any], violations: list[str]) -> dict[str, Any]:
    records = [worker for worker in workers if isinstance(worker, dict)]
    accepted = sum(worker.get("outcome") == "accepted" for worker in records)
    prompts = sum(worker.get("prompt_count", 0) for worker in records if integer(worker.get("prompt_count")))
    corrections = sum(
        worker.get("correction_count", 0)
        for worker in records
        if integer(worker.get("correction_count"))
    )
    usage_records = [worker for worker in records if worker.get("tokens_used") is not None]
    tokens = sum(
        worker.get("tokens_used", 0)
        for worker in usage_records
        if integer(worker.get("tokens_used"))
    )
    score = max(0, 100 - 15 * len(violations))
    return {
        "schema": "herdr-orchestration-eval/v1",
        "phase": phase,
        "decision": "pass" if not violations else "fail",
        "score": score,
        "metrics": {
            "workers": len(records),
            "accepted_outputs": accepted,
            "accepted_output_ratio": round(accepted / len(records), 3) if records else 0,
            "prompts": prompts,
            "corrections": corrections,
            "tokens_used_when_exposed": tokens,
            "token_usage_coverage": round(len(usage_records) / len(records), 3)
            if records
            else 0,
        },
        "violations": violations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("preflight", "final"), required=True)
    parser.add_argument("trace", help="path to herdr-orchestration-run/v1 JSON")
    args = parser.parse_args()
    try:
        with open(args.trace, encoding="utf-8") as handle:
            trace = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        output = result(args.phase, [], [f"cannot read trace: {error}"])
    else:
        output = evaluate(trace, args.phase)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if output["decision"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
