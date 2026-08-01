#!/usr/bin/env bash
# Install the shared policy links. Preview is the default and does not write.
set -euo pipefail

usage() {
  printf 'Usage: %s [--apply] [--replace-symlinks]\n' "${0##*/}"
}

apply=false
replace_symlinks=false
for arg in "$@"; do
  case "$arg" in
    --apply) apply=true ;;
    --replace-symlinks) replace_symlinks=true ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

if "$replace_symlinks" && ! "$apply"; then
  printf '%s\n' '--replace-symlinks requires --apply.' >&2
  exit 2
fi

: "${HOME:?HOME must be set}"
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
repo_root=$(cd -- "$script_dir/.." && pwd -P)
source_file="$repo_root/AGENTS.md"
[[ -f "$source_file" ]] || { printf 'Missing source policy: %s\n' "$source_file" >&2; exit 1; }

targets=(
  "$HOME/.agents/AGENTS.md"
  "$HOME/.codex/AGENTS.md"
  "$HOME/.pi/agent/AGENTS.md"
  "$HOME/.config/opencode/AGENTS.md"
  "$HOME/.claude/CLAUDE.md"
  "$HOME/.grok/AGENTS.md"
  "$HOME/.hermes/AGENTS.md"
)

# Preflight all targets before any parent directory or link is created.
for target in "${targets[@]}"; do
  if [[ -L "$target" ]]; then
    if [[ "$target" -ef "$source_file" ]]; then
      continue
    elif ! "$apply" || ! "$replace_symlinks"; then
      printf 'Refusing different symlink without --replace-symlinks: %s\n' "$target" >&2
      exit 1
    fi
  elif [[ -e "$target" ]]; then
    printf 'Refusing existing non-symlink: %s\n' "$target" >&2
    exit 1
  fi
done

for target in "${targets[@]}"; do
  if [[ -L "$target" && "$target" -ef "$source_file" ]]; then
    printf 'ok: %s\n' "$target"
  elif [[ -L "$target" ]]; then
    rm -f "$target"
    ln -s "$source_file" "$target"
    printf 'replaced symlink: %s\n' "$target"
  elif "$apply"; then
    mkdir -p "$(dirname -- "$target")"
    ln -s "$source_file" "$target"
    printf 'linked: %s\n' "$target"
  else
    printf 'would link: %s\n' "$target"
  fi
done
