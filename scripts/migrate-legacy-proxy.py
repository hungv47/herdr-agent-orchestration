#!/usr/bin/env python3
"""Remove only configuration previously managed by the retired local proxy."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
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


def update_text(path: Path, transform: Callable[[str], str], check: bool, changed: list[str]) -> None:
    if not path.is_file():
        return
    current = path.read_text(encoding="utf-8")
    desired = transform(current)
    if desired == current:
        return
    changed.append(str(path))
    if not check:
        write_atomic(path, desired)


def update_json(path: Path, transform: Callable[[dict[str, Any]], None], check: bool, changed: list[str]) -> None:
    if not path.is_file():
        return
    current = json.loads(path.read_text(encoding="utf-8"))
    desired = json.loads(json.dumps(current))
    transform(desired)
    if desired == current:
        return
    changed.append(str(path))
    if not check:
        write_atomic(path, json.dumps(desired, indent=2) + "\n")


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


def clean_opencode(data: dict[str, Any]) -> None:
    plugins = data.get("plugin")
    if isinstance(plugins, list):
        data["plugin"] = [item for item in plugins if f"{LEGACY}/providers/opencode/" not in str(item)]


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
    hermes = HOME / ".hermes"
    configs = [hermes / "config.yaml", *sorted((hermes / "profiles").glob("*/config.yaml"))]
    for path in configs:
        update_text(path, clean_hermes_yaml, check, changed)
    for path in [hermes / ".env", *sorted((hermes / "profiles").glob("*/.env"))]:
        update_text(path, clean_env, check, changed)

    update_json(HOME / ".config/opencode/opencode.jsonc", clean_opencode, check, changed)
    update_json(HOME / ".pi/agent/models.json", clean_pi, check, changed)
    update_text(HOME / ".local/bin/hermes", clean_wrapper, check, changed)
    update_text(
        HOME / ".hermes/hermes-agent/agent/credential_pool.py",
        reverse_hermes_primary_patch,
        check,
        changed,
    )
    update_text(
        HOME / ".hermes/hermes-agent/agent/auxiliary_client.py",
        reverse_hermes_aux_patch,
        check,
        changed,
    )
    pi = shutil.which("pi")
    if pi:
        pi_api = (
            Path(pi).resolve().parent.parent
            / "node_modules/@earendil-works/pi-ai/dist/api/openai-codex-responses.js"
        )
        update_text(pi_api, reverse_pi_patch, check, changed)

    plugin = hermes / f"plugins/{LEGACY}_retrieve"
    if plugin.is_symlink() and LEGACY in os.readlink(plugin):
        changed.append(str(plugin))
        if not check:
            plugin.unlink()
    state = HOME / f".config/{LEGACY}/ipse-herdr-version"
    if state.exists():
        changed.append(str(state))
        if not check:
            state.unlink()
            try:
                state.parent.rmdir()
            except OSError:
                pass
        executable = shutil.which(LEGACY)
        if executable and not check:
            subprocess.run(
                [executable, "install", "remove", "--profile", "herdr"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
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
