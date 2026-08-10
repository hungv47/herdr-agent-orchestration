#!/usr/bin/env python3
"""Configure OpenCode, Pi GPT, and Hermes to use the local Headroom proxy."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

import yaml

PROXY = "http://127.0.0.1:8787"
BASE_URL = f"{PROXY}/v1"
ROOT = Path(__file__).resolve().parent
HOME = Path.home()


def nested_set(data: dict, dotted: str, value: object) -> None:
    cursor = data
    parts = dotted.split(".")
    for part in parts[:-1]:
        cursor = cursor.setdefault(part, {})
    cursor[parts[-1]] = value


def desired_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    values = {
        "model.base_url": BASE_URL,
        "agent.max_turns": 30,
        "agent.coding_context": "focus",
        "tool_loop_guardrails.hard_stop_enabled": True,
        "tool_loop_guardrails.hard_stop_after.exact_failure": 3,
        "tool_loop_guardrails.hard_stop_after.same_tool_failure": 5,
        "tool_loop_guardrails.hard_stop_after.idempotent_no_progress": 3,
        "tool_loop_guardrails.loop_caps.max_web_searches": 12,
        "tool_loop_guardrails.loop_caps.max_subagents": 2,
        "compression.protect_last_n": 12,
        "compression.proactive_prune_tokens": 48000,
        "compression.idle_compact_after_seconds": 1800,
        "display.compact": True,
        "display.interim_assistant_messages": False,
        "display.tool_progress": False,
        "display.long_running_notifications": False,
        "display.busy_ack_detail": False,
        "delegation.max_iterations": 8,
        "code_execution.max_tool_calls": 30,
    }
    for key, value in values.items():
        nested_set(data, key, value)
    disabled = data.setdefault("agent", {}).setdefault("disabled_toolsets", [])
    if "delegation" not in disabled:
        disabled.append("delegation")
    toolsets = data.setdefault("platform_toolsets", {})
    toolsets["cli"] = ["coding", "headroom"]
    for platform, enabled in list(toolsets.items()):
        if isinstance(enabled, list) and "headroom" not in enabled:
            enabled.append("headroom")
    plugins = data.setdefault("plugins", {}).setdefault("enabled", [])
    for plugin in ("herdr-agent-state", "headroom_retrieve"):
        if plugin not in plugins:
            plugins.append(plugin)
    return data


def yaml_current(path: Path) -> bool:
    if not path.is_file():
        return True
    current = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return current == desired_yaml(path)


def configure_yaml(path: Path, check: bool) -> bool:
    if not path.is_file():
        return True
    desired = desired_yaml(path)
    current = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if current == desired:
        return True
    if check:
        return False
    backup = path.with_suffix(path.suffix + ".pre-headroom")
    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(yaml.safe_dump(desired, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return True


def find_opencode_plugin() -> Path:
    executable = Path(shutil.which("headroom") or "").resolve()
    tool_root = executable.parent.parent
    matches = list(tool_root.glob("lib/python*/site-packages/headroom/providers/opencode/_dist/entry.opencode.js"))
    if len(matches) != 1:
        raise RuntimeError("cannot locate Headroom's packaged OpenCode plugin")
    return matches[0]


def configure_opencode(check: bool) -> bool:
    path = HOME / ".config/opencode/opencode.jsonc"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    plugin = str(find_opencode_plugin())
    entries = [item for item in data.get("plugin", []) if "headroom/providers/opencode/_dist/entry.opencode.js" not in str(item)]
    entries.append(f"file://{plugin}")
    if data.get("plugin") == entries:
        return True
    if check:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not path.with_suffix(path.suffix + ".pre-headroom").exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".pre-headroom"))
    data["plugin"] = entries
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return True


def configure_pi(check: bool) -> bool:
    agent_dir = HOME / ".pi/agent"
    executable = shutil.which("pi")
    if not agent_dir.is_dir() or not executable:
        return True
    package_root = Path(executable).resolve().parent.parent
    api_path = package_root / "node_modules/@earendil-works/pi-ai/dist/api/openai-codex-responses.js"
    old = '''    const normalized = raw.replace(/\\/+$/, "");
    if (normalized.endsWith("/codex/responses"))'''
    new = '''    const normalized = raw.replace(/\\/+$/, "");
    if (normalized.endsWith("/v1"))
        return `${normalized}/responses`;
    if (normalized.endsWith("/codex/responses"))'''
    package_current = patch_text(api_path, old, new, check)
    path = agent_dir / "models.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    providers = data.setdefault("providers", {})
    provider = providers.setdefault("openai-codex", {})
    if provider.get("baseUrl") == BASE_URL:
        return package_current
    if check:
        return False
    if path.exists() and not path.with_suffix(path.suffix + ".pre-headroom").exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".pre-headroom"))
    provider["baseUrl"] = BASE_URL
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return package_current


def set_env(path: Path, check: bool) -> bool:
    if not path.exists():
        return True
    lines = path.read_text(encoding="utf-8").splitlines()
    wanted = f"HERMES_CODEX_BASE_URL={BASE_URL}"
    updated = [line for line in lines if not line.startswith("HERMES_CODEX_BASE_URL=")]
    updated.append(wanted)
    if lines == updated:
        return True
    if check:
        return False
    path.write_text("\n".join(updated) + "\n", encoding="utf-8")
    return True


def patch_text(path: Path, old: str, new: str, check: bool) -> bool:
    if not path.is_file():
        return True
    text = path.read_text(encoding="utf-8")
    if new in text:
        return True
    if old not in text:
        raise RuntimeError(f"unsupported Hermes version: expected text absent in {path}")
    if check:
        return False
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return True


def configure_hermes(check: bool) -> list[str]:
    home = HOME / ".hermes"
    if not home.is_dir():
        return []
    failures: list[str] = []
    plugin_source = ROOT / "headroom/hermes/headroom_retrieve"
    plugin_target = home / "plugins/headroom_retrieve"
    if plugin_target.is_symlink() and plugin_target.resolve() == plugin_source:
        pass
    elif check:
        failures.append(str(plugin_target))
    else:
        if plugin_target.exists() or plugin_target.is_symlink():
            if plugin_target.is_dir() and not plugin_target.is_symlink():
                shutil.rmtree(plugin_target)
            else:
                plugin_target.unlink()
        plugin_target.parent.mkdir(parents=True, exist_ok=True)
        plugin_target.symlink_to(plugin_source)
    config_paths = [home / "config.yaml", *sorted((home / "profiles").glob("*/config.yaml"))]
    for path in config_paths:
        if not configure_yaml(path, check):
            failures.append(str(path))
    env_paths = [home / ".env", *sorted((home / "profiles").glob("*/.env"))]
    for path in env_paths:
        if not set_env(path, check):
            failures.append(str(path))
    agent_root = home / "hermes-agent/agent"
    old_base = '"base_url": "https://chatgpt.com/backend-api/codex",'
    new_base = '"base_url": (\n                        os.getenv("HERMES_CODEX_BASE_URL", "").strip().rstrip("/")\n                        or "https://chatgpt.com/backend-api/codex"\n                    ),'
    if not patch_text(agent_root / "credential_pool.py", old_base, new_base, check):
        failures.append(str(agent_root / "credential_pool.py"))
    old_aux = '_CODEX_AUX_BASE_URL = "https://chatgpt.com/backend-api/codex"'
    new_aux = '_CODEX_AUX_BASE_URL = (\n    os.getenv("HERMES_CODEX_BASE_URL", "").strip().rstrip("/")\n    or "https://chatgpt.com/backend-api/codex"\n)'
    if not patch_text(agent_root / "auxiliary_client.py", old_aux, new_aux, check):
        failures.append(str(agent_root / "auxiliary_client.py"))
    wrapper = HOME / ".local/bin/hermes"
    export = f'export HERMES_CODEX_BASE_URL="{BASE_URL}"'
    if wrapper.is_file():
        text = wrapper.read_text(encoding="utf-8")
        if export not in text:
            if check:
                failures.append(str(wrapper))
            else:
                marker = "unset PYTHONHOME\n"
                if marker not in text:
                    raise RuntimeError(f"unsupported Hermes wrapper: {wrapper}")
                wrapper.write_text(text.replace(marker, marker + export + "\n", 1), encoding="utf-8")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    failures: list[str] = []
    if not configure_opencode(args.check):
        failures.append(str(HOME / ".config/opencode/opencode.jsonc"))
    if not configure_pi(args.check):
        failures.append(str(HOME / ".pi/agent/models.json"))
    failures.extend(configure_hermes(args.check))
    if failures:
        print("Headroom configuration drift:")
        print("\n".join(f"- {path}" for path in failures))
        return 1
    print("Headroom client configuration: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
