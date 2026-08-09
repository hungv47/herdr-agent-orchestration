#!/bin/sh
# Install and verify the token-efficient Headroom path for Hermes, Codex, and OpenCode.

set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VERSION=0.34.0
PROFILE=herdr
STATE="$HOME/.config/headroom/ipse-herdr-version"
HERMES_PY="$HOME/.hermes/hermes-agent/venv/bin/python"

check() {
  command -v headroom >/dev/null 2>&1 || return 1
  headroom --version 2>&1 | grep -Fq "$VERSION" || return 1
  headroom install status --profile "$PROFILE" 2>&1 | grep -Fq 'Healthy:    yes' || return 1
  [ -x "$HERMES_PY" ] || return 1
  "$HERMES_PY" "$ROOT/configure-headroom.py" --check >/dev/null || return 1
}

if [ "${1:-}" = "--check" ]; then
  check && { echo "HEADROOM_OK"; exit 0; }
  echo "HEADROOM_DRIFT" >&2
  exit 1
fi

command -v uv >/dev/null 2>&1 || { echo "uv is required" >&2; exit 1; }
if ! command -v headroom >/dev/null 2>&1 || ! headroom --version 2>&1 | grep -Fq "$VERSION"; then
  uv tool install --force --python 3.13 "headroom-ai[proxy,code]==$VERSION"
fi

if [ ! -f "$STATE" ] || [ "$(cat "$STATE")" != "$VERSION-v2" ] || ! headroom install status --profile "$PROFILE" 2>&1 | grep -Fq 'Healthy:    yes'; then
  headroom install remove --profile "$PROFILE" >/dev/null 2>&1 || true
  headroom install apply \
    --preset persistent-service \
    --scope provider \
    --providers manual \
    --target codex \
    --profile "$PROFILE" \
    --port 8787 \
    --mode token \
    --code-aware \
    --no-telemetry \
    --env HEADROOM_OUTPUT_SHAPER=1 \
    --env OPENAI_TARGET_API_URL=https://chatgpt.com/backend-api/codex \
    --env HEADROOM_EXCLUDE_TOOLS=read_file,headroom_retrieve
  mkdir -p "$(dirname -- "$STATE")"
  printf '%s\n' "$VERSION-v2" >"$STATE"
fi

[ -x "$HERMES_PY" ] || { echo "Hermes Python is required: $HERMES_PY" >&2; exit 1; }
"$HERMES_PY" "$ROOT/configure-headroom.py"
check || { echo "Headroom verification failed" >&2; exit 1; }
echo "HEADROOM_OK"
