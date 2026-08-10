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
  README.md AGENTS.md HERMES-POLICY.md LICENSE .gitignore ATTRIBUTION.md scripts/install.sh scripts/verify.sh
  scripts/herdr-guard scripts/migrate-legacy-proxy.py
  skills/ops-herdr-orchestration/SKILL.md
  skills/ops-herdr-orchestration/references/caveman-activate.md
  skills/ops-herdr-orchestration/scripts/dispatch_worker.py
  skills/ops-herdr-orchestration/scripts/watch_worker.py
  skills/ops-herdr-orchestration/scripts/worker_runtime.py
  skills/ops-herdr-orchestration/scripts/audit_session.py
  skills/ops-herdr-orchestration/scripts/audit_hermes_session.py
  tests/test_dispatch_worker.py
)
for file in "${required[@]}"; do [[ -f "$file" ]] || fail "missing $file"; done
for script in scripts/install.sh scripts/verify.sh scripts/herdr-guard; do bash -n "$script"; done
python3 -m py_compile "$skill_root"/scripts/*.py scripts/migrate-legacy-proxy.py tests/test_dispatch_worker.py
python3 -m unittest discover -s tests -v

[[ $(wc -c <AGENTS.md) -lt 4000 ]] || fail 'AGENTS.md is verbose'
for phrase in \
  'Recommendation: DIY|orchestrate' 'Prefer DIY' 'Policy revision: ipse-orchestration/v9' \
  'Respond terse like smart caveman' \
  'DeepSeek V4 Flash' 'OpenCode' 'Cline' 'GPT-5.6 Luna Max' 'Pi CLI' \
  'Default to one worker' 'at most 1,200 characters' 'eight model iterations' \
  '20k visible output characters' 'A blocked receipt ends the attempt' \
  'cooperative Herdr guard' 'Provider dashboards remain the source of truth' \
  'dispatch_worker.py'; do
  need AGENTS.md "$phrase"
done
for phrase in \
  'tool_loop_guardrails.hard_stop_enabled true' \
  'hard_stop_after.exact_failure 2' \
  'hard_stop_after.same_tool_failure 3' \
  'hard_stop_after.idempotent_no_progress 2' \
  'tools disable delegation --platform cli'; do
  need scripts/install.sh "$phrase"
done
for stale in 'eval_run.py' 'efficiency preflight' 'one corrective prompt' 'wait/retry' 'Cavecrew'; do
  ! grep -Fqi "$stale" AGENTS.md README.md "$skill_root/SKILL.md" || fail "stale ceremony: $stale"
done

test_home="$tmp/home"
fake_bin="$tmp/homebrew/bin"
legacy=head''room
mkdir -p "$test_home/.hermes/profiles/alpha" "$test_home/.hermes/profiles/beta" "$fake_bin"
mkdir -p "$test_home/.config/opencode" "$test_home/.pi/agent" "$test_home/.config/$legacy"
printf 'root identity\n' >"$test_home/.hermes/SOUL.md"
printf 'alpha identity\n' >"$test_home/.hermes/profiles/alpha/SOUL.md"
printf 'beta identity\n' >"$test_home/.hermes/profiles/beta/SOUL.md"
printf 'model:\n  base_url: http://127.0.0.1:8787/v1\nplugins:\n  enabled:\n    - %s_retrieve\n' "$legacy" >"$test_home/.hermes/config.yaml"
printf 'HERMES_CODEX_BASE_URL=http://127.0.0.1:8787/v1\nKEEP=1\n' >"$test_home/.hermes/.env"
printf '{\n  // preserve this comment\n  "plugin": [\n    "file:///tmp/%s/providers/opencode/_dist/entry.opencode.js",\n    "keep",\n  ],\n}\n' "$legacy" >"$test_home/.config/opencode/opencode.jsonc"
printf '{"providers":{"openai-codex":{"baseUrl":"http://127.0.0.1:8787/v1","keep":true}}}\n' >"$test_home/.pi/agent/models.json"
printf 'legacy\n' >"$test_home/.config/$legacy/ipse-herdr-version"
printf '#!/bin/sh\nexit 0\n' >"$fake_bin/herdr"
printf '#!/bin/sh\nexit 0\n' >"$fake_bin/$legacy"
chmod +x "$fake_bin/herdr"
chmod +x "$fake_bin/$legacy"
HOME="$test_home" PATH="$fake_bin:/usr/bin:/bin" bash scripts/install.sh >/dev/null
[[ ! -e "$test_home/.agents/AGENTS.md" ]] || fail 'preview wrote files'
HOME="$test_home" PATH="$fake_bin:/usr/bin:/bin" bash scripts/install.sh --apply >/dev/null
HOME="$test_home" PATH="$fake_bin:/usr/bin:/bin" bash scripts/install.sh --apply >/dev/null
[[ -L "$test_home/.local/bin/herdr" && "$test_home/.local/bin/herdr" -ef "$repo_root/scripts/herdr-guard" ]] \
  || fail 'Herdr guard was not installed'
[[ -x "$test_home/.local/libexec/herdr-real" ]] || fail 'Herdr runtime was not preserved'
if HOME="$test_home" "$test_home/.local/bin/herdr" --session ipse agent start worker >/dev/null 2>&1; then
  fail 'raw Herdr mutation bypassed guard'
fi
HOME="$test_home" IPSE_HERDR_DISPATCH=1 "$test_home/.local/bin/herdr" --session ipse agent start worker \
  || fail 'dispatcher capability could not reach Herdr runtime'
HOME="$test_home" "$test_home/.local/bin/herdr" workspace list \
  || fail 'read-only workspace inspection was blocked'
for target in \
  "$test_home/.agents/AGENTS.md" "$test_home/.codex/AGENTS.md" \
  "$test_home/.pi/agent/AGENTS.md" "$test_home/.config/opencode/AGENTS.md" \
  "$test_home/.claude/CLAUDE.md" "$test_home/.grok/AGENTS.md" "$test_home/.hermes/AGENTS.md"; do
  [[ -L "$target" && "$target" -ef "$repo_root/AGENTS.md" ]] || fail "invalid policy link: $target"
done
for soul in "$test_home/.hermes/SOUL.md" "$test_home/.hermes/profiles/alpha/SOUL.md" "$test_home/.hermes/profiles/beta/SOUL.md"; do
  need "$soul" '<!-- BEGIN IPSE BOUNDED ORCHESTRATION -->'
  need "$soul" 'Respond terse like smart caveman'
  [[ $(grep -Fc '<!-- BEGIN IPSE BOUNDED ORCHESTRATION -->' "$soul") == 1 ]] || fail "duplicate Hermes policy: $soul"
done
need "$test_home/.hermes/SOUL.md" 'root identity'
need "$test_home/.hermes/profiles/alpha/SOUL.md" 'alpha identity'
! grep -Fq '127.0.0.1:8787' "$test_home/.hermes/config.yaml" "$test_home/.pi/agent/models.json" || fail 'legacy base URL survived migration'
! grep -Fqi "$legacy" "$test_home/.hermes/config.yaml" "$test_home/.config/opencode/opencode.jsonc" || fail 'legacy plugin survived migration'
need "$test_home/.hermes/.env" 'KEEP=1'
need "$test_home/.config/opencode/opencode.jsonc" '// preserve this comment'
for target in \
  "$test_home/.agents/skills/ops-herdr-orchestration" \
  "$test_home/.pi/agent/skills/ops-herdr-orchestration" \
  "$test_home/.grok/skills/ops-herdr-orchestration" \
  "$test_home/.hermes/skills/ops-herdr-orchestration" \
  "$test_home/.hermes/profiles/alpha/skills/ops-herdr-orchestration" \
  "$test_home/.hermes/profiles/beta/skills/ops-herdr-orchestration"; do
  [[ -L "$target" && "$target" -ef "$skill_root" ]] || fail "invalid skill link: $target"
done

# Installing before Hermes exists still creates its future always-loaded policy.
pre_hermes_home="$tmp/pre-hermes-home"
mkdir -p "$pre_hermes_home"
HOME="$pre_hermes_home" PATH="$fake_bin:/usr/bin:/bin" bash scripts/install.sh --apply >/dev/null
need "$pre_hermes_home/.hermes/SOUL.md" '<!-- BEGIN IPSE BOUNDED ORCHESTRATION -->'
need "$pre_hermes_home/.hermes/SOUL.md" 'Respond terse like smart caveman'

# A failed legacy teardown must leave its marker and planned changes retryable.
retry_home="$tmp/retry-home"
retry_bin="$tmp/retry-bin"
mkdir -p "$retry_home/.hermes" "$retry_home/.config/$legacy" "$retry_bin"
printf 'base_url: http://127.0.0.1:8787/v1\n' >"$retry_home/.hermes/config.yaml"
printf 'legacy\n' >"$retry_home/.config/$legacy/ipse-herdr-version"
printf '#!/bin/sh\nexit 7\n' >"$retry_bin/$legacy"
chmod +x "$retry_bin/$legacy"
if HOME="$retry_home" PATH="$retry_bin:/usr/bin:/bin" python3 scripts/migrate-legacy-proxy.py >/dev/null 2>&1; then
  fail 'failed legacy teardown unexpectedly succeeded'
fi
[[ -f "$retry_home/.config/$legacy/ipse-herdr-version" ]] || fail 'failed teardown lost retry marker'
need "$retry_home/.hermes/config.yaml" '127.0.0.1:8787'

atomic_home="$tmp/atomic-home"
mkdir -p "$atomic_home/.hermes" "$atomic_home/.pi/agent"
printf 'base_url: http://127.0.0.1:8787/v1\n' >"$atomic_home/.hermes/config.yaml"
printf '{broken\n' >"$atomic_home/.pi/agent/models.json"
if HOME="$atomic_home" PATH=/usr/bin:/bin python3 scripts/migrate-legacy-proxy.py >/dev/null 2>&1; then
  fail 'invalid config unexpectedly migrated'
fi
need "$atomic_home/.hermes/config.yaml" '127.0.0.1:8787'

privacy_pattern='hun'"gvio"'|/Us'"ers"'/|/ho'"me"'/[^[:space:]/]+|[[:alnum:]._%+-]+'"@"'[[:alnum:].-]+\.[[:alpha:]]{2,}'
if grep -REin "$privacy_pattern" --include='*.md' --include='*.py' --include='*.sh' .; then
  fail 'privacy scan failed'
fi

if "$installed"; then
  for target in "$HOME/.agents/AGENTS.md" "$HOME/.codex/AGENTS.md" "$HOME/.pi/agent/AGENTS.md" \
    "$HOME/.config/opencode/AGENTS.md" "$HOME/.claude/CLAUDE.md" "$HOME/.grok/AGENTS.md" "$HOME/.hermes/AGENTS.md"; do
    [[ -L "$target" && "$target" -ef "$repo_root/AGENTS.md" ]] || fail "invalid installed link: $target"
  done
  grep -Fq 'Respond terse like smart caveman' "$HOME/.codex/AGENTS.md" || fail 'Caveman policy drift'
  for target in \
    "$HOME/.agents/skills/ops-herdr-orchestration" \
    "$HOME/.pi/agent/skills/ops-herdr-orchestration" \
    "$HOME/.grok/skills/ops-herdr-orchestration"; do
    [[ -L "$target" && "$target" -ef "$skill_root" ]] || fail "invalid installed skill link: $target"
  done
  if [[ -d "$HOME/.hermes" ]]; then
    target="$HOME/.hermes/skills/ops-herdr-orchestration"
    [[ -L "$target" && "$target" -ef "$skill_root" ]] || fail "invalid installed skill link: $target"
    for profile in "$HOME/.hermes/profiles"/*; do
      [[ -d "$profile" ]] || continue
      target="$profile/skills/ops-herdr-orchestration"
      [[ -L "$target" && "$target" -ef "$skill_root" ]] || fail "invalid installed skill link: $target"
    done
  fi
  if command -v hermes >/dev/null 2>&1; then
    for hermes_home in "$HOME/.hermes" "$HOME/.hermes/profiles"/*; do
      [[ -d "$hermes_home" ]] || continue
      [[ $(HERMES_HOME="$hermes_home" hermes config get agent.max_turns) == 8 ]] || fail "Hermes max_turns drift: $hermes_home"
      [[ $(HERMES_HOME="$hermes_home" hermes config get memory.nudge_interval) == 0 ]] || fail "Hermes memory review drift: $hermes_home"
      [[ $(HERMES_HOME="$hermes_home" hermes config get skills.creation_nudge_interval) == 0 ]] || fail "Hermes skill review drift: $hermes_home"
      [[ $(HERMES_HOME="$hermes_home" hermes config get tool_loop_guardrails.hard_stop_enabled) == true ]] || fail "Hermes hard-stop drift: $hermes_home"
      [[ $(HERMES_HOME="$hermes_home" hermes config get tool_loop_guardrails.hard_stop_after.exact_failure) == 2 ]] || fail "Hermes exact-failure drift: $hermes_home"
      [[ $(HERMES_HOME="$hermes_home" hermes config get tool_loop_guardrails.hard_stop_after.same_tool_failure) == 3 ]] || fail "Hermes same-tool drift: $hermes_home"
      [[ $(HERMES_HOME="$hermes_home" hermes config get tool_loop_guardrails.hard_stop_after.idempotent_no_progress) == 2 ]] || fail "Hermes no-progress drift: $hermes_home"
      [[ $(HERMES_HOME="$hermes_home" hermes config get tool_loop_guardrails.loop_caps.max_subagents) == 1 ]] || fail "Hermes subagent cap drift: $hermes_home"
      [[ $(HERMES_HOME="$hermes_home" hermes config get code_execution.max_tool_calls) == 12 ]] || fail "Hermes tool-call drift: $hermes_home"
      HERMES_HOME="$hermes_home" hermes tools list --platform cli | grep -q 'disabled.*delegation' || fail "Hermes delegation enabled: $hermes_home"
      need "$hermes_home/SOUL.md" 'Respond terse like smart caveman'
    done
  fi
fi

removed_proxy='head''room'
if grep -REin "$removed_proxy" --exclude='*.pyc' --exclude-dir=.git --exclude-dir=__pycache__ .; then
  fail 'removed proxy still referenced'
fi

printf 'Verification passed%s.\n' "$("$installed" && printf ' (installed state checked)')"
