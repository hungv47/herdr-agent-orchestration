#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
repo_root=$(cd -- "$script_dir/.." && pwd -P)
cd "$repo_root"

fail() { printf 'Verification failed: %s\n' "$*" >&2; exit 1; }
need() { grep -Fq "$2" "$1" || fail "$1 missing: $2"; }

required=(
  README.md AGENTS.md ATTRIBUTION.md LICENSE
  evals/README.md evals/example-input.json evals/score_trial.py
  tests/test_score_trial.py scripts/verify.sh .github/workflows/verify.yml
)
for file in "${required[@]}"; do [[ -f "$file" ]] || fail "missing $file"; done

retired=(
  HERMES-POLICY.md scripts/install.sh scripts/herdr-guard scripts/migrate-legacy-proxy.py
  skills/ops-herdr-orchestration/SKILL.md
  skills/ops-herdr-orchestration/scripts/dispatch_worker.py
  skills/ops-herdr-orchestration/scripts/watch_worker.py
  tests/test_dispatch_worker.py
)
for path in "${retired[@]}"; do [[ ! -e "$path" ]] || fail "retired runtime remains: $path"; done

bash -n scripts/verify.sh
python3 -m py_compile evals/score_trial.py tests/test_score_trial.py
python3 -m unittest discover -s tests -v

[[ $(wc -c <AGENTS.md) -lt 3000 ]] || fail 'AGENTS.md exceeds 3 KB'
for phrase in \
  'Decide internally' 'official Herdr skill' 'One worker is the default' \
  'at most 700 characters' 'One concrete repair prompt' \
  'Headroom is an optional data-plane optimization' 'Omit orchestration ceremony'; do
  need AGENTS.md "$phrase"
done

if grep -Fq 'Choose: DIY or orchestrate' AGENTS.md; then
  fail 'mode-choice ceremony returned'
fi

privacy_pattern='/Us''ers/|/ho''me/[^[:space:]/]+|[[:alnum:]._%+-]+'"'@'"'[[:alnum:].-]+\.[[:alpha:]]{2,}'
if grep -REin "$privacy_pattern" --include='*.md' --include='*.py' --include='*.sh' --include='*.json' .; then
  fail 'privacy scan failed'
fi

if python3 evals/score_trial.py evals/example-input.json >/dev/null; then
  fail 'incomplete example unexpectedly passed adoption gate'
fi

printf 'Verification passed.\n'
