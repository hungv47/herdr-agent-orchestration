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
