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

[[ $(wc -c <AGENTS.md) -lt 4800 ]] || fail 'AGENTS.md exceeds 4.8 KB'
for phrase in \
  'global coding-agent contract' 'official `herdr` skill' 'Default to one worker' \
  'never block launch' 'at most one correction' 'Wait on Herdr lifecycle state' \
  'Headroom is the token-efficiency data plane' \
  'Do not run `headroom doctor` as a routine preflight' \
  'installed `pi` command run direct'; do
  need AGENTS.md "$phrase"
done

for retired in 'Choose: DIY or orchestrate' Caveman dispatch_worker.py \
  'at most 700 characters' 'Headroom is experimental and off the execution path'; do
  ! grep -Fqi "$retired" AGENTS.md || fail "retired policy returned: $retired"
done

privacy_pattern='/Us''ers/|/ho''me/[^[:space:]/]+|[[:alnum:]._%+-]+'"'@'"'[[:alnum:].-]+\.[[:alpha:]]{2,}'
if grep -REin "$privacy_pattern" --include='*.md' --include='*.py' --include='*.sh' --include='*.json' .; then
  fail 'privacy scan failed'
fi

if python3 evals/score_trial.py evals/example-input.json >/dev/null; then
  fail 'incomplete example unexpectedly passed adoption gate'
fi

printf 'Verification passed.\n'
