#!/usr/bin/env bash
# Verify the portable policy, budget tools, installer, and optional links.
set -euo pipefail

installed=false
case "${1:-}" in
  '') ;;
  --installed) installed=true ;;
  -h|--help) printf 'Usage: %s [--installed]\n' "${0##*/}"; exit 0 ;;
  *) exit 2 ;;
esac

: "${HOME:?HOME must be set}"
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
repo_root=$(cd -- "$script_dir/.." && pwd -P)
skill="$repo_root/skills/ops-herdr-orchestration"
tmp=$(mktemp -d "${TMPDIR:-/tmp}/herdr-verify.XXXXXX")
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
cd "$repo_root"

fail() { printf 'Verification failed: %s\n' "$*" >&2; exit 1; }
need() { grep -Fq "$2" "$1" || fail "$1 missing: $2"; }

required=(
  README.md AGENTS.md LICENSE ATTRIBUTION.md
  scripts/install.sh scripts/install-headroom.sh scripts/configure-headroom.py scripts/verify.sh
  scripts/headroom/hermes/headroom_retrieve/__init__.py
  scripts/headroom/hermes/headroom_retrieve/plugin.yaml
  skills/ops-herdr-orchestration/SKILL.md
  skills/ops-herdr-orchestration/scripts/audit_session.py
  skills/ops-herdr-orchestration/scripts/watch_worker.py
)
for file in "${required[@]}"; do [[ -f "$file" ]] || fail "missing $file"; done

for script in scripts/install.sh scripts/install-headroom.sh scripts/verify.sh; do
  [[ -x "$script" ]] || fail "not executable: $script"
  bash -n "$script"
done
for script in skills/ops-herdr-orchestration/scripts/audit_session.py skills/ops-herdr-orchestration/scripts/watch_worker.py; do
  [[ -x "$script" ]] || fail "not executable: $script"
done
python3 -m py_compile scripts/configure-headroom.py skills/ops-herdr-orchestration/scripts/audit_session.py skills/ops-herdr-orchestration/scripts/watch_worker.py

for file in AGENTS.md README.md skills/ops-herdr-orchestration/SKILL.md; do
  for phrase in 'Headroom' 'DeepSeek V4 Flash' 'GPT-5.6 Luna' 'Default to one worker' '1,200 characters' '10 minutes' '40 tool calls' 'one corrective prompt' 'five minutes'; do
    need "$file" "$phrase"
  done
done
for stale in 'eval_run.py' 'efficiency preflight' 'cli: Pi CLI' 'OpenCode or Cline CLI' 'run both workers'; do
  ! grep -Fqi "$stale" AGENTS.md README.md skills/ops-herdr-orchestration/SKILL.md ||
    fail "retired ceremony remains: $stale"
done

# One synthetic over-budget transcript proves the audit fails closed.
cat >"$tmp/waste.jsonl" <<'JSON'
{"type":"session","timestamp":"2026-01-01T00:00:00Z"}
{"type":"message","timestamp":"2026-01-01T00:00:01Z","message":{"role":"user","content":[{"type":"text","text":"ship"}]}}
{"type":"message","timestamp":"2026-01-01T00:11:00Z","message":{"role":"assistant","content":[{"type":"toolCall","name":"read"}],"usage":{"input":80001,"output":1}}}
JSON
! python3 "$skill/scripts/audit_session.py" "$tmp/waste.jsonl" >/dev/null ||
  fail "over-budget transcript passed"

# Installer preview is inert; apply links all existing Hermes profiles.
test_home="$tmp/home"
mkdir -p "$test_home/.hermes/profiles/alpha"
mkdir -p "$test_home/.buzz"
printf '%s\n' '# Buzz Nest' >"$test_home/.buzz/AGENTS.md"
HOME="$test_home" bash scripts/install.sh >/dev/null
[[ ! -e "$test_home/.agents/AGENTS.md" ]] || fail "preview wrote files"
HOME="$test_home" bash scripts/install.sh --apply >/dev/null
for target in "$test_home/.agents/AGENTS.md" "$test_home/.codex/AGENTS.md" "$test_home/.config/opencode/AGENTS.md" "$test_home/.hermes/AGENTS.md"; do
  [[ -L "$target" && "$target" -ef "$repo_root/AGENTS.md" ]] || fail "bad policy link: $target"
done
[[ -L "$test_home/.hermes/profiles/alpha/skills/ops-herdr-orchestration" ]] ||
  fail "missing profile skill link"
need "$test_home/.buzz/AGENTS.md" '<!-- BEGIN HERDR ORCHESTRATION -->'
need "$test_home/.buzz/AGENTS.md" 'Headroom must be healthy'

privacy_pattern='hun'"gvio"'|/Us'"ers"'/|/ho'"me"'/[^[:space:]/]+|[[:alnum:]._%+-]+'"@"'[[:alnum:].-]+\.[[:alpha:]]{2,}'
public_text=(
  README.md AGENTS.md ATTRIBUTION.md
  scripts/install.sh scripts/install-headroom.sh scripts/configure-headroom.py scripts/verify.sh
  scripts/headroom/hermes/headroom_retrieve/__init__.py
  skills/ops-herdr-orchestration/SKILL.md
  skills/ops-herdr-orchestration/scripts/audit_session.py
  skills/ops-herdr-orchestration/scripts/watch_worker.py
)
for file in "${public_text[@]}"; do
  ! grep -Ein "$privacy_pattern" "$file" || fail "privacy scan failed: $file"
done

if "$installed"; then
  for target in "$HOME/.agents/AGENTS.md" "$HOME/.codex/AGENTS.md" "$HOME/.config/opencode/AGENTS.md" "$HOME/.hermes/AGENTS.md"; do
    [[ -L "$target" && "$target" -ef "$repo_root/AGENTS.md" ]] ||
      fail "bad installed policy link: $target"
  done
fi

printf 'Verification passed.\n'
