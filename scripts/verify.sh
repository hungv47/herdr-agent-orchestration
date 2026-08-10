#!/usr/bin/env bash
set -euo pipefail

installed=false
case "${1:-}" in
  '') ;;
  --installed) installed=true ;;
  -h|--help) printf 'Usage: %s [--installed]\n' "${0##*/}"; exit 0 ;;
  *) exit 2 ;;
esac

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
repo_root=$(cd -- "$script_dir/.." && pwd -P)
skill_root="$repo_root/skills/ops-herdr-orchestration"
tmp=$(mktemp -d "${TMPDIR:-/tmp}/herdr-public-verify.XXXXXX")
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
cd "$repo_root"

fail() { printf 'Verification failed: %s\n' "$*" >&2; exit 1; }
need() { grep -Fq "$2" "$1" || fail "$1 missing: $2"; }

required=(
  README.md AGENTS.md LICENSE .gitignore ATTRIBUTION.md scripts/install.sh scripts/verify.sh
  scripts/herdr-guard scripts/install-headroom.sh scripts/configure-headroom.py
  skills/ops-herdr-orchestration/SKILL.md
  skills/ops-herdr-orchestration/scripts/dispatch_worker.py
  skills/ops-herdr-orchestration/scripts/watch_worker.py
  skills/ops-herdr-orchestration/scripts/worker_runtime.py
  skills/ops-herdr-orchestration/scripts/audit_session.py
  skills/ops-herdr-orchestration/scripts/audit_hermes_session.py
  tests/test_dispatch_worker.py
)
for file in "${required[@]}"; do [[ -f "$file" ]] || fail "missing $file"; done
for script in scripts/install.sh scripts/verify.sh scripts/herdr-guard; do bash -n "$script"; done
sh -n scripts/install-headroom.sh
python3 -m py_compile "$skill_root"/scripts/*.py tests/test_dispatch_worker.py
python3 -m unittest discover -s tests -v

[[ $(wc -c <AGENTS.md) -lt 4000 ]] || fail 'AGENTS.md is verbose'
for phrase in \
  'Recommendation: DIY|orchestrate' 'Prefer DIY' 'Headroom must be healthy' \
  'DeepSeek V4 Flash' 'OpenCode' 'Cline' 'GPT-5.6 Luna Max' 'Pi CLI' \
  'Default to one worker' 'at most 1,200 characters' 'eight model iterations' \
  'five model requests' '50k uncached input tokens' 'A blocked receipt ends the attempt' \
  'installed Herdr guard' '$5 daily budget' \
  'dispatch_worker.py'; do
  need AGENTS.md "$phrase"
done
for stale in 'eval_run.py' 'efficiency preflight' 'one corrective prompt' 'wait/retry' '40 Headroom requests'; do
  ! grep -Fqi "$stale" AGENTS.md README.md "$skill_root/SKILL.md" || fail "stale ceremony: $stale"
done

test_home="$tmp/home"
mkdir -p "$test_home/.hermes/profiles/alpha" "$test_home/.hermes/profiles/beta"
mkdir -p "$test_home/.local/bin"
printf '#!/bin/sh\nexit 0\n' >"$test_home/.local/bin/herdr"
chmod +x "$test_home/.local/bin/herdr"
HOME="$test_home" PATH=/usr/bin:/bin bash scripts/install.sh >/dev/null
[[ ! -e "$test_home/.agents/AGENTS.md" ]] || fail 'preview wrote files'
HOME="$test_home" PATH=/usr/bin:/bin bash scripts/install.sh --apply >/dev/null
[[ -L "$test_home/.local/bin/herdr" && "$test_home/.local/bin/herdr" -ef "$repo_root/scripts/herdr-guard" ]] \
  || fail 'Herdr guard was not installed'
[[ -x "$test_home/.local/libexec/herdr-real" ]] || fail 'Herdr runtime was not preserved'
if HOME="$test_home" "$test_home/.local/bin/herdr" --session ipse agent start worker >/dev/null 2>&1; then
  fail 'raw Herdr mutation bypassed guard'
fi
HOME="$test_home" IPSE_HERDR_DISPATCH=1 "$test_home/.local/bin/herdr" --session ipse agent start worker \
  || fail 'dispatcher capability could not reach Herdr runtime'
for target in \
  "$test_home/.agents/AGENTS.md" "$test_home/.codex/AGENTS.md" \
  "$test_home/.pi/agent/AGENTS.md" "$test_home/.config/opencode/AGENTS.md" \
  "$test_home/.claude/CLAUDE.md" "$test_home/.grok/AGENTS.md" "$test_home/.hermes/AGENTS.md"; do
  [[ -L "$target" && "$target" -ef "$repo_root/AGENTS.md" ]] || fail "invalid policy link: $target"
done
for target in \
  "$test_home/.agents/skills/ops-herdr-orchestration" \
  "$test_home/.pi/agent/skills/ops-herdr-orchestration" \
  "$test_home/.grok/skills/ops-herdr-orchestration" \
  "$test_home/.hermes/skills/ops-herdr-orchestration" \
  "$test_home/.hermes/profiles/alpha/skills/ops-herdr-orchestration" \
  "$test_home/.hermes/profiles/beta/skills/ops-herdr-orchestration"; do
  [[ -L "$target" && "$target" -ef "$skill_root" ]] || fail "invalid skill link: $target"
done

privacy_pattern='hun'"gvio"'|/Us'"ers"'/|/ho'"me"'/[^[:space:]/]+|[[:alnum:]._%+-]+'"@"'[[:alnum:].-]+\.[[:alpha:]]{2,}'
if grep -REin "$privacy_pattern" --include='*.md' --include='*.py' --include='*.sh' .; then
  fail 'privacy scan failed'
fi

if "$installed"; then
  for target in "$HOME/.agents/AGENTS.md" "$HOME/.codex/AGENTS.md" "$HOME/.pi/agent/AGENTS.md" \
    "$HOME/.config/opencode/AGENTS.md" "$HOME/.claude/CLAUDE.md" "$HOME/.grok/AGENTS.md" "$HOME/.hermes/AGENTS.md"; do
    [[ -L "$target" && "$target" -ef "$repo_root/AGENTS.md" ]] || fail "invalid installed link: $target"
  done
  command -v headroom >/dev/null 2>&1 || fail 'Headroom is not installed'
  headroom doctor 2>&1 | grep -Fq '0 failure(s)' || fail 'Headroom is unhealthy'
  if command -v hermes >/dev/null 2>&1; then
    [[ $(hermes config get agent.max_turns) == 8 ]] || fail 'Hermes max_turns drift'
    [[ $(hermes config get memory.nudge_interval) == 0 ]] || fail 'Hermes memory review drift'
    [[ $(hermes config get skills.creation_nudge_interval) == 0 ]] || fail 'Hermes skill review drift'
    [[ $(hermes config get tool_loop_guardrails.loop_caps.max_subagents) == 1 ]] || fail 'Hermes subagent cap drift'
    [[ $(hermes config get code_execution.max_tool_calls) == 12 ]] || fail 'Hermes tool-call drift'
  fi
fi

printf 'Verification passed%s.\n' "$("$installed" && printf ' (installed state checked)')"
