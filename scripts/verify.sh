#!/usr/bin/env bash
# Verify the public package, evaluator behavior, installer, and optional live links.
set -euo pipefail

usage() {
  printf 'Usage: %s [--installed]\n' "${0##*/}"
}

installed=false
case "${1:-}" in
  '') ;;
  --installed) installed=true ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac
[[ $# -le 1 ]] || { usage >&2; exit 2; }

: "${HOME:?HOME must be set}"
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
repo_root=$(cd -- "$script_dir/.." && pwd -P)
skill_root="$repo_root/skills/ops-herdr-orchestration"
eval_script="$skill_root/scripts/eval_run.py"
tmp=$(mktemp -d "${TMPDIR:-/tmp}/herdr-public-verify.XXXXXX")
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
cd "$repo_root"

fail() {
  printf 'Verification failed: %s\n' "$*" >&2
  exit 1
}

need() {
  grep -Fq "$2" "$1" || fail "$1 missing: $2"
}

required_files=(
  README.md AGENTS.md LICENSE .gitignore ATTRIBUTION.md
  assets/cover.png
  assets/brand/SOURCES.md
  assets/brand/buzz-icon.png
  assets/brand/codexbar-icon.png
  assets/brand/herdr-logo.svg
  assets/brand/hermes-logo.png
  scripts/install.sh scripts/verify.sh
  skills/ops-herdr-orchestration/SKILL.md
  skills/ops-herdr-orchestration/references/efficiency-eval.md
  skills/ops-herdr-orchestration/scripts/eval_run.py
)
for file in "${required_files[@]}"; do
  [[ -f "$file" ]] || fail "missing required file: $file"
done

for script in scripts/install.sh scripts/verify.sh; do
  [[ -x "$script" ]] || fail "script is not executable: $script"
  bash -n "$script"
done
[[ -x "$eval_script" ]] || fail "evaluator is not executable"
python3 -m py_compile "$eval_script"

for file in AGENTS.md README.md; do
  for phrase in \
    'Recommendation: DIY|orchestrate' \
    'Choose: DIY or orchestrate' \
    'strongest available reasoning model' \
    'cheaper or free models' \
    'expected execution savings' \
    'exactly two' \
    'model: DeepSeek V4 Flash' \
    'effort: xhigh' \
    'cli: OpenCode or Cline CLI' \
    'model: GPT-5.6 Luna' \
    'effort: Max' \
    'cli: Pi CLI' \
    'Never use a third model or harness' \
    'not an automatic duplicate pair' \
    'whole, independently verifiable deliverable' \
    'verifiable bridge' \
    'at most one corrective prompt' \
    'A timeout is not evidence'; do
    need "$file" "$phrase"
  done
  [[ $(grep -c '^  - model:' "$file") -eq 2 ]] || fail "$file worker pool is not exactly two entries"
  for stale in \
    'model: Grok 4.5' \
    'Cline CLI only' \
    'cli: Codex CLI or Pi CLI' \
    'Never use a fourth model or harness' \
    'OpenCode and Cline CLIs in parallel'; do
    ! grep -Fq "$stale" "$file" || fail "$file retains stale routing: $stale"
  done
done

for phrase in \
  'Default to one worker' \
  'fewest whole, independently verifiable deliverables' \
  'strongest available reasoning model' \
  'cheaper or free models' \
  'outbound bridge' \
  'inbound bridge' \
  'one initial brief plus one correction' \
  'efficiency preflight' \
  'final eval'; do
  need "$skill_root/SKILL.md" "$phrase"
done

for phrase in \
  'accepted-output ratio' \
  'prompt loops' \
  'token budgets' \
  'compact outbound bridge' \
  'compact inbound bridge'; do
  need "$skill_root/references/efficiency-eval.md" "$phrase"
done

# Behavioral eval: useful independent work passes; granular work, overlap,
# retry loops, and budget overruns fail.
cat >"$tmp/good.json" <<'JSON'
{
  "schema": "herdr-orchestration-run/v1",
  "objective": "Ship two independent verified outputs",
  "workers": [
    {
      "id": "docs", "deliverable": "Publish and verify the complete operator contract",
      "delegation_reason": "parallel-independent", "writable_paths": ["docs/contract.md"],
      "semantic_surfaces": ["operator-contract"], "runtime_resources": [],
      "acceptance": ["test -s docs/contract.md"], "stop_condition": "stop on scope conflict",
      "return_format": "changed paths and evidence", "parallel_group": "wave-1", "depends_on": [],
      "prompt_count": 1, "correction_count": 0, "same_blocker_repeated": false,
      "outcome": "accepted", "result_used": true, "evidence": ["contract check passed"],
      "closure_reason": null, "token_budget": 8000, "tokens_used": 5000
    },
    {
      "id": "test", "deliverable": "Add and verify the independent regression coverage",
      "delegation_reason": "parallel-independent", "writable_paths": ["tests/contract.sh"],
      "semantic_surfaces": ["contract-test"], "runtime_resources": [],
      "acceptance": ["bash tests/contract.sh"], "stop_condition": "stop on scope conflict",
      "return_format": "changed paths and evidence", "parallel_group": "wave-1", "depends_on": [],
      "prompt_count": 2, "correction_count": 1, "same_blocker_repeated": false,
      "outcome": "accepted", "result_used": true, "evidence": ["test passed"],
      "closure_reason": null, "token_budget": null, "tokens_used": null
    }
  ]
}
JSON
python3 "$eval_script" --phase preflight "$tmp/good.json" >/dev/null || fail "good preflight rejected"
python3 "$eval_script" --phase final "$tmp/good.json" >/dev/null || fail "good final eval rejected"

cat >"$tmp/granular.json" <<'JSON'
{"schema":"herdr-orchestration-run/v1","objective":"Look around","workers":[{"id":"reader","deliverable":"Inspect","delegation_reason":"specialization","writable_paths":[],"semantic_surfaces":[],"runtime_resources":[],"acceptance":[],"stop_condition":"","return_format":"notes","parallel_group":null,"depends_on":[],"prompt_count":0,"correction_count":0,"same_blocker_repeated":false,"outcome":"pending","result_used":false,"evidence":[],"closure_reason":null,"token_budget":null,"tokens_used":null}]}
JSON
! python3 "$eval_script" --phase preflight "$tmp/granular.json" >/dev/null 2>&1 || fail "granular brief passed"

cat >"$tmp/overlap.json" <<'JSON'
{"schema":"herdr-orchestration-run/v1","objective":"Parallel edits","workers":[{"id":"a","deliverable":"Finish and verify the first complete output","delegation_reason":"parallel-independent","writable_paths":["shared/config"],"semantic_surfaces":["config"],"runtime_resources":[],"acceptance":["check a"],"stop_condition":"stop","return_format":"evidence","parallel_group":"wave","depends_on":[],"prompt_count":0,"correction_count":0,"same_blocker_repeated":false,"outcome":"pending","result_used":false,"evidence":[],"closure_reason":null,"token_budget":null,"tokens_used":null},{"id":"b","deliverable":"Finish and verify the second complete output","delegation_reason":"parallel-independent","writable_paths":["shared"],"semantic_surfaces":["config"],"runtime_resources":[],"acceptance":["check b"],"stop_condition":"stop","return_format":"evidence","parallel_group":"wave","depends_on":[],"prompt_count":0,"correction_count":0,"same_blocker_repeated":false,"outcome":"pending","result_used":false,"evidence":[],"closure_reason":null,"token_budget":null,"tokens_used":null}]}
JSON
! python3 "$eval_script" --phase preflight "$tmp/overlap.json" >/dev/null 2>&1 || fail "overlapping parallel work passed"

cat >"$tmp/loop.json" <<'JSON'
{"schema":"herdr-orchestration-run/v1","objective":"Ship one output","workers":[{"id":"loop","deliverable":"Finish and verify the complete requested output","delegation_reason":"specialization","writable_paths":["out.md"],"semantic_surfaces":["output"],"runtime_resources":[],"acceptance":["test -s out.md"],"stop_condition":"stop after correction","return_format":"evidence","parallel_group":null,"depends_on":[],"prompt_count":4,"correction_count":3,"same_blocker_repeated":true,"outcome":"blocked","result_used":false,"evidence":[],"closure_reason":"same blocker repeated","token_budget":5000,"tokens_used":9000}]}
JSON
! python3 "$eval_script" --phase final "$tmp/loop.json" >/dev/null 2>&1 || fail "prompt loop passed"

# Installer preview must not create files; apply must wire policies, global skills,
# and every existing Hermes profile to this checkout.
test_home="$tmp/home"
mkdir -p "$test_home/.hermes/profiles/alpha" "$test_home/.hermes/profiles/beta"
HOME="$test_home" bash scripts/install.sh >/dev/null
[[ ! -e "$test_home/.agents/AGENTS.md" ]] || fail "installer preview wrote files"
HOME="$test_home" bash scripts/install.sh --apply >/dev/null
for target in \
  "$test_home/.agents/AGENTS.md" \
  "$test_home/.codex/AGENTS.md" \
  "$test_home/.pi/agent/AGENTS.md" \
  "$test_home/.config/opencode/AGENTS.md" \
  "$test_home/.claude/CLAUDE.md" \
  "$test_home/.grok/AGENTS.md" \
  "$test_home/.hermes/AGENTS.md"; do
  [[ -L "$target" && "$target" -ef "$repo_root/AGENTS.md" ]] || fail "invalid test policy link: $target"
done
for target in \
  "$test_home/.agents/skills/ops-herdr-orchestration" \
  "$test_home/.pi/agent/skills/ops-herdr-orchestration" \
  "$test_home/.grok/skills/ops-herdr-orchestration" \
  "$test_home/.hermes/skills/ops-herdr-orchestration" \
  "$test_home/.hermes/profiles/alpha/skills/ops-herdr-orchestration" \
  "$test_home/.hermes/profiles/beta/skills/ops-herdr-orchestration"; do
  [[ -L "$target" && "$target" -ef "$skill_root" ]] || fail "invalid test skill link: $target"
done

# Build sensitive terms without keeping private strings contiguous in source.
privacy_pattern='hun'"gvio"'|/Us'"ers"'/|/ho'"me"'/[^[:space:]/]+|[[:alnum:]._%+-]+'"@"'[[:alnum:].-]+\.[[:alpha:]]{2,}|[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}'
public_text=(
  README.md AGENTS.md LICENSE .gitignore ATTRIBUTION.md
  assets/brand/SOURCES.md assets/brand/herdr-logo.svg
  scripts/install.sh scripts/verify.sh
  skills/ops-herdr-orchestration/SKILL.md
  skills/ops-herdr-orchestration/references/efficiency-eval.md
  skills/ops-herdr-orchestration/scripts/eval_run.py
)
for file in "${public_text[@]}"; do
  if grep -Ein "$privacy_pattern" "$file"; then
    fail "privacy scan failed: $file"
  fi
done

if "$installed"; then
  for target in \
    "$HOME/.agents/AGENTS.md" \
    "$HOME/.codex/AGENTS.md" \
    "$HOME/.pi/agent/AGENTS.md" \
    "$HOME/.config/opencode/AGENTS.md" \
    "$HOME/.claude/CLAUDE.md" \
    "$HOME/.grok/AGENTS.md" \
    "$HOME/.hermes/AGENTS.md"; do
    [[ -L "$target" && "$target" -ef "$repo_root/AGENTS.md" ]] || fail "invalid installed policy link: $target"
  done
  for target in \
    "$HOME/.agents/skills/ops-herdr-orchestration" \
    "$HOME/.pi/agent/skills/ops-herdr-orchestration" \
    "$HOME/.grok/skills/ops-herdr-orchestration" \
    "$HOME/.hermes/skills/ops-herdr-orchestration"; do
    [[ -L "$target" && "$target" -ef "$skill_root" ]] || fail "invalid installed skill link: $target"
  done
  if [[ -d "$HOME/.hermes/profiles" ]]; then
    for profile in "$HOME/.hermes/profiles"/*; do
      [[ -d "$profile" ]] || continue
      target="$profile/skills/ops-herdr-orchestration"
      [[ -L "$target" && "$target" -ef "$skill_root" ]] || fail "invalid profile skill link: $target"
    done
  fi
fi

printf 'Verification passed%s.\n' "$("$installed" && printf ' (installed links checked)')"
