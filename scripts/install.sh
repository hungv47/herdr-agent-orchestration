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
source_skill="$repo_root/skills/ops-herdr-orchestration"
guard_source="$repo_root/scripts/herdr-guard"
guard_front="$HOME/.local/bin/herdr"
guard_real="$HOME/.local/libexec/herdr-real"
guard_available=true
guard_external=$(command -v herdr 2>/dev/null || true)
[[ -f "$source_file" ]] || { printf 'Missing source policy: %s\n' "$source_file" >&2; exit 1; }
[[ -f "$source_skill/SKILL.md" ]] || { printf 'Missing source skill: %s\n' "$source_skill" >&2; exit 1; }
[[ -x "$guard_source" ]] || { printf 'Missing executable Herdr guard: %s\n' "$guard_source" >&2; exit 1; }

policy_targets=(
  "$HOME/.agents/AGENTS.md"
  "$HOME/.codex/AGENTS.md"
  "$HOME/.pi/agent/AGENTS.md"
  "$HOME/.config/opencode/AGENTS.md"
  "$HOME/.claude/CLAUDE.md"
  "$HOME/.grok/AGENTS.md"
  "$HOME/.hermes/AGENTS.md"
)

skill_targets=(
  "$HOME/.agents/skills/ops-herdr-orchestration"
  "$HOME/.pi/agent/skills/ops-herdr-orchestration"
  "$HOME/.grok/skills/ops-herdr-orchestration"
  "$HOME/.hermes/skills/ops-herdr-orchestration"
)
if [[ -d "$HOME/.hermes/profiles" ]]; then
  for profile in "$HOME/.hermes/profiles"/*; do
    [[ -d "$profile" ]] || continue
    skill_targets+=("$profile/skills/ops-herdr-orchestration")
  done
fi

preflight_target() {
  local source=$1 target=$2
  if [[ -L "$target" ]]; then
    if [[ "$target" -ef "$source" ]]; then
      return
    elif ! "$apply" || ! "$replace_symlinks"; then
      printf 'Refusing different symlink without --replace-symlinks: %s\n' "$target" >&2
      exit 1
    fi
  elif [[ -e "$target" ]]; then
    printf 'Refusing existing non-symlink: %s\n' "$target" >&2
    exit 1
  fi
}

# Preflight every policy and skill target before creating anything.
for target in "${policy_targets[@]}"; do
  preflight_target "$source_file" "$target"
done
for target in "${skill_targets[@]}"; do
  preflight_target "$source_skill" "$target"
done
if [[ -L "$guard_front" && $(readlink "$guard_front") != "$guard_source" ]]; then
  printf 'Refusing unrelated Herdr symlink: %s\n' "$guard_front" >&2
  exit 1
fi
if [[ ! -e "$guard_front" && ! -e "$guard_real" && -z "$guard_external" ]]; then
  guard_available=false
fi

install_target() {
  local source=$1 target=$2 label=$3
  if [[ -L "$target" && "$target" -ef "$source" ]]; then
    printf 'ok: %s\n' "$target"
  elif [[ -L "$target" ]]; then
    rm -f "$target"
    ln -s "$source" "$target"
    printf 'replaced symlink: %s\n' "$target"
  elif "$apply"; then
    mkdir -p "$(dirname -- "$target")"
    ln -s "$source" "$target"
    printf 'linked %s: %s\n' "$label" "$target"
  else
    printf 'would link %s: %s\n' "$label" "$target"
  fi
}

for target in "${policy_targets[@]}"; do
  install_target "$source_file" "$target" policy
done
for target in "${skill_targets[@]}"; do
  install_target "$source_skill" "$target" skill
done

install_herdr_guard() {
  if ! "$guard_available"; then
    printf 'skip Herdr guard: runtime is not installed\n'
    return
  fi
  if ! "$apply"; then
    printf 'would guard Herdr mutations: %s\n' "$guard_front"
    return
  fi
  mkdir -p "$(dirname -- "$guard_front")" "$(dirname -- "$guard_real")"
  if [[ ! -e "$guard_front" && ! -e "$guard_real" && -n "$guard_external" ]]; then
    ln -s "$guard_external" "$guard_real"
  fi
  if [[ ! -L "$guard_front" && -e "$guard_front" ]]; then
    if [[ -e "$guard_real" ]]; then
      previous="$guard_real.previous-$(date +%Y%m%d-%H%M%S)-$$"
      mv "$guard_real" "$previous"
      printf 'archived prior Herdr runtime: %s\n' "$previous"
    fi
    mv "$guard_front" "$guard_real"
  fi
  [[ -L "$guard_front" ]] || ln -s "$guard_source" "$guard_front"
  [[ -x "$guard_real" ]] || { printf 'Herdr runtime is not executable: %s\n' "$guard_real" >&2; exit 1; }
  printf 'guarded Herdr mutations: %s\n' "$guard_front"
}

install_herdr_guard

configure_hermes_home() {
  local hermes_home=$1
  command -v hermes >/dev/null 2>&1 || return 0
  if ! "$apply"; then
    printf 'would configure Hermes ceilings: %s\n' "$hermes_home"
    return
  fi
  HERMES_HOME="$hermes_home" hermes config set --force agent.max_turns 8 >/dev/null
  HERMES_HOME="$hermes_home" hermes config set --force memory.nudge_interval 0 >/dev/null
  HERMES_HOME="$hermes_home" hermes config set --force skills.creation_nudge_interval 0 >/dev/null
  HERMES_HOME="$hermes_home" hermes config set --force tool_loop_guardrails.loop_caps.max_subagents 1 >/dev/null
  HERMES_HOME="$hermes_home" hermes config set --force code_execution.max_tool_calls 12 >/dev/null
  printf 'configured Hermes ceilings: %s\n' "$hermes_home"
}

configure_hermes_home "$HOME/.hermes"
if [[ -d "$HOME/.hermes/profiles" ]]; then
  for profile in "$HOME/.hermes/profiles"/*; do
    [[ -d "$profile" ]] || continue
    configure_hermes_home "$profile"
  done
fi
