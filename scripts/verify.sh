#!/usr/bin/env bash
# Verify the public repository and, optionally, the installed policy links.
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
cd "$repo_root"

required_files=(
  README.md AGENTS.md LICENSE .gitignore ATTRIBUTION.md
  assets/cover.png
  assets/brand/SOURCES.md
  assets/brand/buzz-icon.png
  assets/brand/codexbar-icon.png
  assets/brand/herdr-logo.svg
  assets/brand/hermes-logo.png
  scripts/install.sh scripts/verify.sh
)
for file in "${required_files[@]}"; do
  [[ -f "$file" ]] || { printf 'Missing required file: %s\n' "$file" >&2; exit 1; }
done

check_routing_policy() {
  local file=$1
  local deepseek_line luna_line grok_line phrase
  local required_phrases=(
    'ordered default/fallback'
    'exactly three'
    'model: DeepSeek V4 Flash'
    'effort: xhigh'
    'cli: Cline CLI'
    'Cline CLI only'
    'normal first-choice worker'
    'model: GPT-5.6 Luna'
    'effort: Max only'
    'cli: Codex CLI or Pi CLI'
    'Max effort is mandatory'
    'model: Grok 4.5'
    'effort: high'
    'cli: Grok CLI'
    'final fallback'
    'DeepSeek V4 Flash at xhigh'
    'GPT-5.6 Luna at Max only'
    'Grok 4.5 at high'
    'wait/retry/report blocked'
    'Never use a fourth model or harness'
    'scope, risk, and authorization'
    'safety/authorization gate'
  )
  for phrase in "${required_phrases[@]}"; do
    grep -Fq "$phrase" "$file" || {
      printf 'Routing policy missing in %s: %s\n' "$file" "$phrase" >&2
      exit 1
    }
  done

  deepseek_line=$(grep -n -m1 -F '  - model: DeepSeek V4 Flash' "$file" | cut -d: -f1)
  luna_line=$(grep -n -m1 -F '  - model: GPT-5.6 Luna' "$file" | cut -d: -f1)
  grok_line=$(grep -n -m1 -F '  - model: Grok 4.5' "$file" | cut -d: -f1)
  if (( deepseek_line >= luna_line || luna_line >= grok_line )); then
    printf 'Routing policy order is not DeepSeek → Luna → Grok in %s\n' "$file" >&2
    exit 1
  fi

  for stale in \
    'highest-ranked approved option' \
    'high-judgment worker' \
    'Fan out independent, bounded support or review' \
    'Grok 4.5 primary' \
    'DeepSeek V4 Flash support-only' \
    'Luna at high'; do
    ! grep -Fq "$stale" "$file" || {
      printf 'Stale routing policy in %s: %s\n' "$file" "$stale" >&2
      exit 1
    }
  done
  ! grep -Fq 'cli: OpenCode or Cline CLI' "$file" || {
    printf 'Stale DeepSeek OpenCode mapping in %s\n' "$file" >&2
    exit 1
  }
  ! grep -Fq 'DeepSeek V4 Flash at xhigh via OpenCode' "$file" || {
    printf 'Stale DeepSeek OpenCode mapping in %s\n' "$file" >&2
    exit 1
  }
}

check_routing_policy AGENTS.md
check_routing_policy README.md

for script in scripts/install.sh scripts/verify.sh; do
  [[ -x "$script" ]] || { printf 'Script is not executable: %s\n' "$script" >&2; exit 1; }
  bash -n "$script"
done

# Build sensitive terms without embedding those private strings as contiguous source text.
privacy_pattern='hun'"gvio"'|ip'"se"'|/Us'"ers"'/|/ho'"me"'/[^[:space:]/]+|[[:alnum:]._%+-]+'"@"'[[:alnum:].-]+\.[[:alpha:]]{2,}|[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}'
public_text=(
  README.md AGENTS.md LICENSE .gitignore ATTRIBUTION.md
  assets/brand/SOURCES.md assets/brand/herdr-logo.svg
  scripts/install.sh scripts/verify.sh
)
for file in "${public_text[@]}"; do
  if grep -Ein "$privacy_pattern" "$file"; then
    printf 'Privacy scan failed: %s\n' "$file" >&2
    exit 1
  fi
done

if "$installed"; then
  source_file="$repo_root/AGENTS.md"
  targets=(
    "$HOME/.agents/AGENTS.md"
    "$HOME/.codex/AGENTS.md"
    "$HOME/.pi/agent/AGENTS.md"
    "$HOME/.config/opencode/AGENTS.md"
    "$HOME/.claude/CLAUDE.md"
    "$HOME/.grok/AGENTS.md"
    "$HOME/.hermes/AGENTS.md"
  )
  for target in "${targets[@]}"; do
    [[ -L "$target" && "$target" -ef "$source_file" ]] || {
      printf 'Invalid installed policy link: %s\n' "$target" >&2
      exit 1
    }
  done
fi

printf 'Verification passed%s.\n' "$($installed && printf ' (installed links checked)')"
