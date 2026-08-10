#!/usr/bin/env python3
"""Launch exactly one bounded Herdr worker and return a compact receipt."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, NamedTuple

from worker_runtime import headroom_requests, herdr as run


BRIEF_LIMIT = 1_200
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
RECEIPT_RE = re.compile(r"(?im)^\s*(accepted|blocked)\s*:\s*(.+)$")
DEFAULT_BUDGET = {
    "max_seconds": 480,
    "idle_seconds": 120,
    "max_requests": 8,
    "max_uncached_input_tokens": 80_000,
    "max_output_tokens": 8_000,
}
SUBSTANTIAL_BUDGET = {
    "max_seconds": 900,
    "idle_seconds": 120,
    "max_requests": 12,
    "max_uncached_input_tokens": 140_000,
    "max_output_tokens": 16_000,
}


class Route(NamedTuple):
    name: str
    args: tuple[str, ...]
    headroom_agent: str | None


def parse_brief(brief: str) -> dict[str, str]:
    if len(brief) > BRIEF_LIMIT:
        raise ValueError("brief exceeds the 1,200 character limit")
    lines = [line.strip() for line in brief.splitlines() if line.strip()]
    if len(lines) != 5:
        raise ValueError("brief must contain exactly five non-empty lines")
    if not lines[0].startswith("role=worker; outcome="):
        raise ValueError("line 1 must start with 'role=worker; outcome='")
    parsed = {"outcome": lines[0].split("outcome=", 1)[1].strip()}
    for line, field in zip(lines[1:], ("write", "non-goals", "accept", "return")):
        prefix = f"{field}="
        if not line.startswith(prefix):
            raise ValueError(f"expected '{prefix}' in the compact bridge")
        parsed[field] = line[len(prefix) :].strip()
    if any(not value for value in parsed.values()):
        raise ValueError("compact bridge fields must not be empty")
    receipt_contract = parsed["return"].lower()
    required_receipt = ("accepted|blocked:", "paths=", "checks=", "blocker=", "then stop")
    if any(part not in receipt_contract for part in required_receipt):
        raise ValueError("return must require accepted|blocked: paths=; checks=; blocker=; then stop")
    return parsed


def build_route(name: str, gpt_model: str = "gpt-5.6-luna") -> Route:
    if name == "opencode":
        return Route("opencode", ("-m", "opencode/deepseek-v4-flash-free"), "opencode")
    if name == "cline":
        return Route(
            "cline",
            (
                "--provider",
                "cline",
                "--model",
                "deepseek/deepseek-v4-flash",
                "--thinking",
                "xhigh",
                "--compaction",
                "agentic",
                "--retries",
                "1",
                "--timeout",
                "600",
            ),
            None,
        )
    if name == "pi":
        return Route("pi", ("--model", f"openai-codex/{gpt_model}:max"), "codex")
    raise ValueError(f"unsupported route: {name}")


def choose_route(
    available: set[str],
    gpt_reason: str | None,
    gpt_model: str = "gpt-5.6-luna",
    requested: str = "auto",
) -> Route:
    if requested != "auto":
        if requested not in available:
            raise ValueError(f"requested {requested} route is unavailable")
        if requested == "pi" and not gpt_reason:
            raise ValueError("Pi requires a GPT reason")
        if requested != "pi" and gpt_reason:
            raise ValueError("a GPT reason requires the Pi route")
        return build_route(requested, gpt_model)
    if gpt_reason:
        if "pi" not in available:
            raise ValueError("GPT was requested but Pi is unavailable")
        return build_route("pi", gpt_model)
    for name in ("opencode", "cline"):
        if name in available:
            return build_route(name, gpt_model)
    raise ValueError("no approved free route is available; Pi requires a GPT reason")


def parse_receipt(output: str) -> tuple[str, str]:
    clean = ANSI_RE.sub("", output)
    matches = list(RECEIPT_RE.finditer(clean))
    if not matches:
        return "blocked", "missing accepted|blocked worker receipt"
    match = matches[-1]
    fields: dict[str, str] = {}
    for part in match.group(2).split(";"):
        key, separator, value = part.strip().partition("=")
        if separator and key.strip().lower() in {"paths", "checks", "blocker"}:
            fields[key.strip().lower()] = " ".join(value.split())
    if any(not fields.get(key) for key in ("paths", "checks", "blocker")):
        return "blocked", "incomplete worker receipt; require paths=, checks=, blocker="
    evidence = "; ".join(f"{key}={fields[key]}" for key in ("paths", "checks", "blocker"))
    return match.group(1).lower(), evidence[:600]


def normalize_reason(label: str, value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} must not be blank")
    if "\n" in normalized or len(normalized) > 200:
        raise ValueError(f"{label} must be one concise line")
    return normalized


def require_ok(result: subprocess.CompletedProcess[str], label: str) -> str:
    if result.returncode:
        detail = (result.stderr or result.stdout).strip().replace("\n", " ")[:500]
        raise RuntimeError(f"{label} failed: {detail or f'exit {result.returncode}'}")
    return result.stdout


def find_pane_id(value: object) -> str | None:
    if isinstance(value, dict):
        pane_id = value.get("pane_id")
        if isinstance(pane_id, str):
            return pane_id
        for child in value.values():
            found = find_pane_id(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = find_pane_id(child)
            if found:
                return found
    return None


def safe_state_root() -> Path:
    root = Path(os.environ.get("TMPDIR", "/tmp")) / f"ipse-worker-dispatch-{os.getuid()}"
    if root.exists():
        info = root.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid():
            raise RuntimeError(f"unsafe dispatch state root: {root}")
    else:
        root.mkdir(mode=0o700)
    root.chmod(0o700)
    return root


@contextmanager
def deliverable_lock(deliverable: str) -> Iterator[str]:
    digest = hashlib.sha256(deliverable.encode()).hexdigest()[:20]
    path = safe_state_root() / f"{digest}.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    handle = os.fdopen(fd, "w+")
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(f"duplicate deliverable is already running: {digest}") from error
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps({"pid": os.getpid(), "deliverable": digest}) + "\n")
        handle.flush()
        yield digest
    finally:
        handle.close()


@contextmanager
def route_lock(route: str) -> Iterator[None]:
    """Serialize each harness lane so Headroom usage stays attributable."""
    path = safe_state_root() / f"route-{route}.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    handle = os.fdopen(fd, "w+")
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(f"{route} route is already running a worker") from error
        yield
    finally:
        handle.close()


def available_routes() -> set[str]:
    return {name for name in ("opencode", "cline", "pi") if shutil.which(name)}


def result_error_code(result: subprocess.CompletedProcess[str]) -> str | None:
    stream = result.stdout or result.stderr
    try:
        return json.loads(stream).get("error", {}).get("code")
    except (AttributeError, json.JSONDecodeError):
        return None


def start_worker(session: str, name: str, route: Route, pane_id: str) -> subprocess.CompletedProcess[str]:
    result: subprocess.CompletedProcess[str] | None = None
    for attempt in range(5):
        result = run(
            session,
            "agent",
            "start",
            name,
            "--kind",
            route.name,
            "--pane",
            pane_id,
            "--timeout",
            "20000",
            "--",
            *route.args,
        )
        if result.returncode == 0 or result_error_code(result) != "agent_pane_busy":
            return result
        time.sleep(0.25 * (attempt + 1))
    assert result is not None
    return result


def health_gate() -> None:
    if not shutil.which("headroom"):
        raise RuntimeError("Headroom is unavailable")
    try:
        result = subprocess.run(
            ["headroom", "doctor"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("Headroom health gate timed out after 30s") from error
    if result.returncode != 0 and "0 failure(s)" not in result.stdout:
        require_ok(result, "Headroom health gate")


def wait_for_shell(session: str, pane_id: str, *, timeout: float = 10, interval: float = 0.1) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = run(session, "pane", "process-info", "--pane", pane_id)
        if result.returncode == 0:
            try:
                info = json.loads(result.stdout)["result"]["process_info"]
                shell_pid = info["shell_pid"]
                if any(process.get("pid") == shell_pid for process in info.get("foreground_processes", [])):
                    return
            except (KeyError, TypeError, json.JSONDecodeError):
                pass
        time.sleep(interval)
    raise RuntimeError(f"pane {pane_id} did not reach an interactive shell prompt")


def compact_result(status: str, **details: object) -> None:
    print(json.dumps({"status": status, **details}, separators=(",", ":"), sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True, choices=("ipse", "biz", "work"))
    parser.add_argument("--name", required=True)
    parser.add_argument("--cwd", required=True, type=Path)
    parser.add_argument("--brief-file", required=True, type=Path)
    parser.add_argument("--route", default="auto", choices=("auto", "opencode", "cline", "pi"))
    parser.add_argument("--route-reason")
    parser.add_argument("--gpt-reason")
    parser.add_argument(
        "--gpt-model",
        default="gpt-5.6-luna",
        choices=("gpt-5.6-luna", "gpt-5.6-sol", "gpt-5.6-terra"),
    )
    parser.add_argument("--substantial-reason")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    pane_id: str | None = None
    started = False
    try:
        if not NAME_RE.fullmatch(args.name):
            raise ValueError("name must be 1-64 safe identifier characters")
        cwd = args.cwd.expanduser().resolve(strict=True)
        if not cwd.is_dir():
            raise ValueError("cwd must be a directory")
        brief = args.brief_file.read_text(encoding="utf-8").strip()
        fields = parse_brief(brief)
        route_reason = normalize_reason("route reason", args.route_reason)
        gpt_reason = normalize_reason("gpt reason", args.gpt_reason)
        substantial_reason = normalize_reason("substantial reason", args.substantial_reason)
        if args.route != "auto" and not route_reason:
            raise ValueError("an explicit route requires --route-reason")
        if args.route == "auto" and route_reason:
            raise ValueError("--route-reason requires an explicit --route")
        if args.gpt_model != "gpt-5.6-luna" and not gpt_reason:
            raise ValueError("a stronger GPT model requires --gpt-reason")
        route = choose_route(available_routes(), gpt_reason, args.gpt_model, args.route)
        budget = SUBSTANTIAL_BUDGET if substantial_reason else DEFAULT_BUDGET
        deliverable = "\n".join(fields[key] for key in ("outcome", "write", "accept"))

        with deliverable_lock(deliverable) as deliverable_id, route_lock(route.name):
            if args.dry_run:
                compact_result(
                    "accepted",
                    dry_run=True,
                    route=route.name,
                    deliverable=deliverable_id,
                    budget=budget,
                )
                return 0

            duplicate = run(args.session, "agent", "get", args.name)
            if duplicate.returncode == 0:
                raise RuntimeError(f"agent name already exists: {args.name}")
            duplicate_error = result_error_code(duplicate)
            if duplicate_error != "agent_not_found":
                require_ok(duplicate, "duplicate-agent check")
            health_gate()
            baseline_keys = (
                [request.key for request in headroom_requests(route.headroom_agent)]
                if route.headroom_agent
                else []
            )
            split_output = require_ok(
                run(
                    args.session,
                    "pane",
                    "split",
                    "--current",
                    "--direction",
                    "right",
                    "--cwd",
                    str(cwd),
                    "--env",
                    "AGENT_ROLE=worker",
                    "--no-focus",
                ),
                "pane creation",
            )
            pane_id = find_pane_id(json.loads(split_output))
            if not pane_id:
                raise RuntimeError("pane creation returned no pane id")
            wait_for_shell(args.session, pane_id)
            require_ok(start_worker(args.session, args.name, route, pane_id), "worker start")
            started = True
            require_ok(run(args.session, "agent", "prompt", args.name, brief), "initial prompt")

            watcher = Path(__file__).resolve().with_name("watch_worker.py")
            watcher_args = [
                sys.executable,
                str(watcher),
                "--session",
                args.session,
                "--agent",
                args.name,
                "--max-seconds",
                str(budget["max_seconds"]),
                "--idle-seconds",
                str(budget["idle_seconds"]),
                "--max-requests",
                str(budget["max_requests"]),
                "--max-uncached-input-tokens",
                str(budget["max_uncached_input_tokens"]),
                "--max-output-tokens",
                str(budget["max_output_tokens"]),
            ]
            if route.headroom_agent:
                watcher_args.extend(("--headroom-agent", route.headroom_agent))
                for key in baseline_keys:
                    watcher_args.extend(("--baseline-request-key", key))
            watched = subprocess.run(
                watcher_args,
                check=False,
                capture_output=True,
                text=True,
                timeout=budget["max_seconds"] + 60,
            )
            screen = run(args.session, "agent", "read", args.name, "--source", "recent-unwrapped", "--lines", "120")
            receipt_status, evidence = parse_receipt(screen.stdout if screen.returncode == 0 else "")
            watcher_data: dict[str, object] = {}
            try:
                watcher_data = json.loads(watched.stdout.strip().splitlines()[-1])
            except (IndexError, json.JSONDecodeError):
                watcher_data = {"reason": "invalid watcher receipt"}
            status = "accepted" if watched.returncode == 0 and receipt_status == "accepted" else "blocked"
            compact_result(
                status,
                route=route.name,
                deliverable=deliverable_id,
                evidence=evidence,
                watcher=watcher_data,
            )
            return 0 if status == "accepted" else 2
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as error:
        if started:
            run(args.session, "agent", "send-keys", args.name, "ctrl+c")
        compact_result("blocked", reason=str(error))
        return 2
    finally:
        if pane_id:
            run(args.session, "pane", "close", pane_id)


if __name__ == "__main__":
    raise SystemExit(main())
