#!/usr/bin/env python3
"""Remove only configuration previously managed by the retired local proxy."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any, Callable


LEGACY = "head" + "room"
LEGACY_BASE_URL = "http://127.0.0.1:8787/v1"
HOME = Path.home()


def write_atomic(path: Path, text: str) -> None:
    backup = path.with_suffix(path.suffix + ".pre-direct-routing")
    if not backup.exists():
        shutil.copy2(path, backup)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        shutil.copymode(path, temporary)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def plan_text(
    path: Path,
    transform: Callable[[str], str],
    updates: list[tuple[Path, str]],
    changed: list[str],
) -> None:
    if not path.is_file():
        return
    current = path.read_text(encoding="utf-8")
    desired = transform(current)
    if desired == current:
        return
    changed.append(str(path))
    updates.append((path, desired))


def plan_json(
    path: Path,
    transform: Callable[[dict[str, Any]], None],
    updates: list[tuple[Path, str]],
    changed: list[str],
) -> None:
    if not path.is_file():
        return
    current = json.loads(path.read_text(encoding="utf-8"))
    desired = json.loads(json.dumps(current))
    transform(desired)
    if desired == current:
        return
    changed.append(str(path))
    updates.append((path, json.dumps(desired, indent=2) + "\n"))


def strip_jsonc(text: str) -> str:
    """Remove JSONC comments/trailing commas for validation without rewriting the file."""
    output = list(text)
    in_string = False
    escaped = False
    index = 0
    while index < len(output):
        char = output[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if char == "/" and index + 1 < len(output) and output[index + 1] == "/":
            output[index] = output[index + 1] = " "
            index += 2
            while index < len(output) and output[index] not in "\r\n":
                output[index] = " "
                index += 1
            continue
        if char == "/" and index + 1 < len(output) and output[index + 1] == "*":
            output[index] = output[index + 1] = " "
            index += 2
            while index + 1 < len(output) and not (output[index] == "*" and output[index + 1] == "/"):
                if output[index] not in "\r\n":
                    output[index] = " "
                index += 1
            if index + 1 < len(output):
                output[index] = output[index + 1] = " "
                index += 2
            continue
        index += 1

    output = list("".join(output))
    in_string = False
    escaped = False
    for index, char in enumerate(output):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == ",":
            lookahead = index + 1
            while lookahead < len(output) and output[lookahead].isspace():
                lookahead += 1
            if lookahead < len(output) and output[lookahead] in "]}":
                output[index] = " "
    return "".join(output)


JSON_STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"')


def next_significant(text: str, start: int) -> int:
    index = start
    while index < len(text):
        if text[index].isspace():
            index += 1
        elif text.startswith("//", index):
            newline = text.find("\n", index + 2)
            index = len(text) if newline < 0 else newline + 1
        elif text.startswith("/*", index):
            end = text.find("*/", index + 2)
            index = len(text) if end < 0 else end + 2
        else:
            break
    return index


def clean_opencode_jsonc(text: str) -> str:
    """Remove legacy plugin strings while preserving valid JSONC formatting/comments."""
    data = json.loads(strip_jsonc(text))
    if not isinstance(data, dict):
        raise ValueError("OpenCode JSONC root must be an object")
    plugins = data.get("plugin")
    legacy_plugins = {
        item
        for item in plugins
        if isinstance(item, str) and f"{LEGACY}/providers/opencode/" in item
    } if isinstance(plugins, list) else set()
    if not legacy_plugins:
        return text

    removals: list[tuple[int, int]] = []
    for match in JSON_STRING_RE.finditer(text):
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if value not in legacy_plugins:
            continue
        end = match.end()
        significant = next_significant(text, end)
        if significant < len(text) and text[significant] == ",":
            end = significant + 1
        removals.append((match.start(), end))

    desired = text
    for start, end in reversed(removals):
        desired = desired[:start] + desired[end:]
    parsed = json.loads(strip_jsonc(desired))
    expected = json.loads(json.dumps(data))
    expected["plugin"] = [item for item in plugins if item not in legacy_plugins]
    if parsed != expected:
        raise ValueError("OpenCode JSONC legacy-plugin removal could not be verified")
    return desired


def clean_hermes_yaml(text: str) -> str:
    """Remove exact legacy scalars/list items without reformatting user YAML."""
    legacy_lines = {
        f"base_url: {LEGACY_BASE_URL}",
        f'base_url: "{LEGACY_BASE_URL}"',
        f"base_url: '{LEGACY_BASE_URL}'",
        f"- {LEGACY}",
        f"- {LEGACY}_retrieve",
    }
    lines = [line for line in text.splitlines() if line.strip() not in legacy_lines]
    return "\n".join(lines) + ("\n" if lines else "")


def clean_pi(data: dict[str, Any]) -> None:
    providers = data.get("providers")
    provider = providers.get("openai-codex") if isinstance(providers, dict) else None
    if isinstance(provider, dict) and provider.get("baseUrl") == LEGACY_BASE_URL:
        provider.pop("baseUrl", None)


def clean_env(text: str) -> str:
    lines = [
        line
        for line in text.splitlines()
        if line != f"HERMES_CODEX_BASE_URL={LEGACY_BASE_URL}"
    ]
    return "\n".join(lines) + ("\n" if lines else "")


def clean_wrapper(text: str) -> str:
    export = f'export HERMES_CODEX_BASE_URL="{LEGACY_BASE_URL}"\n'
    return text.replace(export, "", 1)


def reverse_pi_patch(text: str) -> str:
    patched = '''    const normalized = raw.replace(/\\/+$/, "");
    if (normalized.endsWith("/v1"))
        return `${normalized}/responses`;
    if (normalized.endsWith("/codex/responses"))'''
    original = '''    const normalized = raw.replace(/\\/+$/, "");
    if (normalized.endsWith("/codex/responses"))'''
    return text.replace(patched, original, 1)


def reverse_hermes_primary_patch(text: str) -> str:
    patched = '''"base_url": (
                        os.getenv("HERMES_CODEX_BASE_URL", "").strip().rstrip("/")
                        or "https://chatgpt.com/backend-api/codex"
                    ),'''
    original = '"base_url": "https://chatgpt.com/backend-api/codex",'
    return text.replace(patched, original, 1)


def reverse_hermes_aux_patch(text: str) -> str:
    patched = '''_CODEX_AUX_BASE_URL = (
    os.getenv("HERMES_CODEX_BASE_URL", "").strip().rstrip("/")
    or "https://chatgpt.com/backend-api/codex"
)'''
    original = '_CODEX_AUX_BASE_URL = "https://chatgpt.com/backend-api/codex"'
    return text.replace(patched, original, 1)


def migrate(check: bool) -> list[str]:
    changed: list[str] = []
    updates: list[tuple[Path, str]] = []
    hermes = HOME / ".hermes"
    configs = [hermes / "config.yaml", *sorted((hermes / "profiles").glob("*/config.yaml"))]
    for path in configs:
        plan_text(path, clean_hermes_yaml, updates, changed)
    for path in [hermes / ".env", *sorted((hermes / "profiles").glob("*/.env"))]:
        plan_text(path, clean_env, updates, changed)

    plan_text(HOME / ".config/opencode/opencode.jsonc", clean_opencode_jsonc, updates, changed)
    plan_json(HOME / ".pi/agent/models.json", clean_pi, updates, changed)
    plan_text(HOME / ".local/bin/hermes", clean_wrapper, updates, changed)
    plan_text(
        HOME / ".hermes/hermes-agent/agent/credential_pool.py",
        reverse_hermes_primary_patch,
        updates,
        changed,
    )
    plan_text(
        HOME / ".hermes/hermes-agent/agent/auxiliary_client.py",
        reverse_hermes_aux_patch,
        updates,
        changed,
    )
    pi = shutil.which("pi")
    if pi:
        pi_api = (
            Path(pi).resolve().parent.parent
            / "node_modules/@earendil-works/pi-ai/dist/api/openai-codex-responses.js"
        )
        plan_text(pi_api, reverse_pi_patch, updates, changed)

    plugin = hermes / f"plugins/{LEGACY}_retrieve"
    remove_plugin = plugin.is_symlink() and LEGACY in os.readlink(plugin)
    if remove_plugin:
        changed.append(str(plugin))
    state = HOME / f".config/{LEGACY}/ipse-herdr-version"
    if state.exists():
        changed.append(str(state))
        executable = shutil.which(LEGACY)
        if not check:
            if not executable:
                raise RuntimeError(f"legacy uninstall is required; retry marker preserved: {state}")
            subprocess.run(
                [executable, "install", "remove", "--profile", "herdr"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
    if check:
        return changed

    for path, desired in updates:
        write_atomic(path, desired)
    if remove_plugin:
        plugin.unlink()
    if state.exists():
        state.unlink()
        try:
            state.parent.rmdir()
        except OSError:
            pass
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    changed = migrate(args.check)
    print(json.dumps({"status": "drift" if changed else "clean", "paths": changed}, separators=(",", ":")))
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
