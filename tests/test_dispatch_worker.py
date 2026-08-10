#!/usr/bin/env python3
"""Focused contract tests for the bounded Herdr dispatcher."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "ops-herdr-orchestration"
    / "scripts"
    / "dispatch_worker.py"
)
WATCHER = SCRIPT.with_name("watch_worker.py")
sys.path.insert(0, str(SCRIPT.parent))


def load_dispatcher():
    spec = importlib.util.spec_from_file_location("dispatch_worker", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DispatchWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dispatch = load_dispatcher()
        spec = importlib.util.spec_from_file_location("watch_worker", WATCHER)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load {WATCHER}")
        cls.watcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.watcher)

    def test_compact_bridge_accepts_exact_contract(self) -> None:
        brief = "\n".join(
            (
                "role=worker; outcome=implement one verified guard",
                "write=src/guard.py tests/test_guard.py",
                "non-goals=no external actions; no delegation",
                "accept=python3 -m unittest tests.test_guard",
                "return=accepted|blocked: paths=<paths>; checks=<checks>; blocker=<blocker>; then stop",
            )
        )
        parsed = self.dispatch.parse_brief(brief)
        self.assertEqual(parsed["outcome"], "implement one verified guard")
        self.assertIn("accepted|blocked", parsed["return"])

    def test_compact_bridge_rejects_extra_or_oversized_work(self) -> None:
        valid = "\n".join(
            (
                "role=worker; outcome=one result",
                "write=src/guard.py",
                "non-goals=no external actions",
                "accept=python3 -m unittest",
                "return=accepted|blocked: paths=<paths>; checks=<checks>; blocker=<blocker>; then stop",
            )
        )
        with self.assertRaisesRegex(ValueError, "exactly five"):
            self.dispatch.parse_brief(valid + "\nplan=first narrate everything")
        with self.assertRaisesRegex(ValueError, "1,200"):
            self.dispatch.parse_brief(valid.replace("one result", "x" * 1200))

    def test_route_order_prefers_free_workers_and_requires_gpt_reason(self) -> None:
        choose = self.dispatch.choose_route
        self.assertEqual(choose({"opencode", "cline", "pi"}, None).name, "opencode")
        self.assertEqual(choose({"cline", "pi"}, None).name, "cline")
        with self.assertRaisesRegex(ValueError, "GPT reason"):
            choose({"pi"}, None)
        self.assertEqual(choose({"opencode", "pi"}, "needs GPT reasoning").name, "pi")
        with self.assertRaisesRegex(ValueError, "Pi is unavailable"):
            choose({"opencode"}, "needs GPT reasoning")
        self.assertEqual(choose({"opencode", "cline"}, None, requested="cline").name, "cline")
        with self.assertRaisesRegex(ValueError, "Pi requires"):
            choose({"pi"}, None, requested="pi")

    def test_receipt_is_fail_closed(self) -> None:
        parse = self.dispatch.parse_receipt
        self.assertEqual(parse("work\naccepted: paths=a; checks=ok; blocker=none")[0], "accepted")
        self.assertEqual(parse("blocked: paths=none; checks=failed; blocker=quota")[0], "blocked")
        self.assertEqual(parse("accepted: looks good")[0], "blocked")
        self.assertEqual(parse("looks good but no receipt")[0], "blocked")

    def test_usage_limits_fail_closed_at_the_ceiling(self) -> None:
        reason = self.watcher.usage_limit_reason
        below = {"requests": 7, "uncached_input_tokens": 79_999, "output_tokens": 7_999}
        self.assertIsNone(reason(below, 8, 80_000, 8_000))
        self.assertEqual(reason({**below, "requests": 8}, 8, 80_000, 8_000), "request_limit")
        self.assertEqual(
            reason({**below, "uncached_input_tokens": 80_000}, 8, 80_000, 8_000),
            "uncached_input_token_limit",
        )

    def test_status_reads_real_nested_herdr_payload(self) -> None:
        payload = {"result": {"agent": {"agent_status": "working"}, "type": "agent_info"}}
        self.assertEqual(self.watcher.parse_status(payload), "working")
        self.assertEqual(self.watcher.parse_status({"agent_status": "done"}), "done")
        self.assertEqual(self.watcher.parse_status({}), "unknown")

    def test_real_headroom_stats_shape_enforces_usage(self) -> None:
        payload = {
            "summary": {"mode": "token"},
            "agent_usage": {
                "agents": [
                    {"agent": "opencode", "requests": 41, "after_tokens": 81_000, "output_tokens": 21_000}
                ]
            },
        }
        self.assertEqual(self.dispatch.headroom_requests.__module__, "worker_runtime")
        runtime = sys.modules["worker_runtime"]
        self.assertEqual(runtime.parse_headroom_totals(payload, "opencode"), (41, 81_000, 21_000))

    def test_headroom_requests_charge_uncached_not_replayed_context(self) -> None:
        runtime = sys.modules["worker_runtime"]
        payload = {
            "request_logs": [
                {
                    "request_id": "r1",
                    "timestamp": "2026-01-01T00:00:00",
                    "model": "deepseek-v4-flash-free",
                    "input_tokens_optimized": 60_000,
                    "uncached_input_tokens": 4_000,
                    "output_tokens": 300,
                    "tags": {"client": "opencode"},
                },
                {
                    "request_id": "r2",
                    "timestamp": "2026-01-01T00:00:01",
                    "model": "gpt-5.6-luna",
                    "input_tokens_optimized": 70_000,
                    "uncached_input_tokens": 2_000,
                    "output_tokens": 100,
                    "tags": {"client": "codex"},
                },
            ]
        }
        requests = runtime.parse_headroom_requests(payload, "opencode")
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].uncached_input_tokens, 4_000)
        self.assertEqual(requests[0].gross_input_tokens, 60_000)

    def test_watcher_counts_each_recent_request_once(self) -> None:
        runtime = sys.modules["worker_runtime"]
        request = runtime.HeadroomRequest("r1", 2_000, 60_000, 100)
        deltas = {
            "requests": 0,
            "uncached_input_tokens": 0,
            "gross_input_tokens": 0,
            "output_tokens": 0,
        }
        with mock.patch.object(self.watcher, "headroom_requests", return_value=[request]):
            seen: set[str] = set()
            self.watcher.add_new_requests("opencode", seen, deltas)
            self.watcher.add_new_requests("opencode", seen, deltas)
        self.assertEqual(deltas["requests"], 1)
        self.assertEqual(deltas["uncached_input_tokens"], 2_000)
        self.assertEqual(deltas["gross_input_tokens"], 60_000)

    def test_route_lock_rejects_parallel_same_harness(self) -> None:
        with self.dispatch.route_lock("opencode"):
            with self.assertRaisesRegex(RuntimeError, "already running"):
                with self.dispatch.route_lock("opencode"):
                    self.fail("second same-route lock unexpectedly succeeded")

    def test_silent_and_repeated_failures_are_bounded(self) -> None:
        self.assertTrue(self.watcher.idle_limit_reached(0, 300, 300))
        output = "\n".join(("Error 101: provider unavailable", "Error 202: provider unavailable", "Error 303: provider unavailable"))
        self.assertEqual(self.watcher.repeated_failure_signature(output), "error #: provider unavailable")

    def test_reasons_must_be_concise_and_nonblank(self) -> None:
        self.assertEqual(self.dispatch.normalize_reason("gpt reason", "  hard reasoning  "), "hard reasoning")
        with self.assertRaisesRegex(ValueError, "must not be blank"):
            self.dispatch.normalize_reason("gpt reason", "   ")

    def test_headroom_health_gate_accepts_warning_only_doctor_exit(self) -> None:
        warning_only = subprocess.CompletedProcess(
            ["headroom", "doctor"],
            1,
            stdout="0 failure(s), 3 warning(s)\n",
            stderr="",
        )
        with mock.patch.object(self.dispatch.shutil, "which", return_value="/usr/local/bin/headroom"), mock.patch.object(
            self.dispatch.subprocess, "run", return_value=warning_only
        ):
            self.dispatch.health_gate()

    def test_headroom_health_gate_rejects_unlimited_spend(self) -> None:
        unlimited = subprocess.CompletedProcess(
            ["headroom", "doctor"],
            1,
            stdout="0 failure(s), 1 warning(s): no budget configured - spend is unlimited\n",
            stderr="",
        )
        with mock.patch.object(self.dispatch.shutil, "which", return_value="/usr/local/bin/headroom"), mock.patch.object(
            self.dispatch.subprocess, "run", return_value=unlimited
        ):
            with self.assertRaisesRegex(RuntimeError, "no spend budget"):
                self.dispatch.health_gate()

    def test_worker_start_retries_a_new_pane_until_its_shell_is_ready(self) -> None:
        busy = subprocess.CompletedProcess(
            ["herdr"],
            1,
            stdout="",
            stderr='{"error":{"code":"agent_pane_busy"}}',
        )
        ready = subprocess.CompletedProcess(["herdr"], 0, stdout="{}", stderr="")
        route = self.dispatch.Route("opencode", ("-m", "model"), "opencode")
        with mock.patch.object(self.dispatch, "run", side_effect=(busy, ready)) as run, mock.patch.object(
            self.dispatch.time, "sleep"
        ):
            result = self.dispatch.start_worker("work", "worker", route, "w1:p2")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(run.call_count, 2)

    def test_wait_for_shell_retries_until_new_pane_is_ready(self) -> None:
        busy = subprocess.CompletedProcess(
            [], 0, stdout='{"result":{"process_info":{"shell_pid":10,"foreground_processes":[{"pid":11}]}}}', stderr=""
        )
        ready = subprocess.CompletedProcess(
            [], 0, stdout='{"result":{"process_info":{"shell_pid":10,"foreground_processes":[{"pid":10}]}}}', stderr=""
        )
        with mock.patch.object(self.dispatch, "run", side_effect=(busy, ready)) as run:
            self.dispatch.wait_for_shell("work", "w2:p2", timeout=1, interval=0)
        self.assertEqual(run.call_count, 2)

    def test_route_config_is_verified_per_selected_client(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            opencode = home / ".config/opencode/opencode.jsonc"
            opencode.parent.mkdir(parents=True)
            opencode.write_text(
                json.dumps({"plugin": ["file:///tmp/headroom/providers/opencode/_dist/entry.opencode.js"]}),
                encoding="utf-8",
            )
            pi = home / ".pi/agent/models.json"
            pi.parent.mkdir(parents=True)
            pi.write_text(
                json.dumps({"providers": {"openai-codex": {"baseUrl": self.dispatch.PI_BASE_URL}}}),
                encoding="utf-8",
            )
            with mock.patch.object(self.dispatch.Path, "home", return_value=home):
                self.dispatch.verify_route_config(self.dispatch.build_route("opencode"))
                self.dispatch.verify_route_config(self.dispatch.build_route("pi"))
                opencode.write_text("{}", encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "not routed through Headroom"):
                    self.dispatch.verify_route_config(self.dispatch.build_route("opencode"))

    def test_cleanup_requires_exact_pane_to_be_gone(self) -> None:
        ok = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        missing = subprocess.CompletedProcess(
            [], 1, stdout='{"error":{"code":"pane_not_found"}}', stderr=""
        )
        with mock.patch.object(self.dispatch, "run", side_effect=(ok, ok, missing)):
            self.assertIsNone(self.dispatch.cleanup_worker("ipse", "worker", "%9", True))
        with mock.patch.object(self.dispatch, "run", return_value=ok), mock.patch.object(
            self.dispatch.time, "sleep"
        ):
            self.assertIn("still present", self.dispatch.cleanup_worker("ipse", "worker", "%9", True))

    def test_herdr_guard_blocks_raw_mutations_but_allows_dispatcher(self) -> None:
        guard = Path(__file__).resolve().parents[1] / "scripts/herdr-guard"
        with tempfile.TemporaryDirectory() as directory:
            real = Path(directory) / "herdr-real"
            real.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            real.chmod(0o700)
            env = {**os.environ, "IPSE_HERDR_REAL_BIN": str(real)}
            blocked = subprocess.run(
                [str(guard), "--session", "ipse", "agent", "start", "w"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(blocked.returncode, 64)
            allowed = subprocess.run(
                [str(guard), "--session", "ipse", "agent", "list"],
                check=False,
                env=env,
            )
            self.assertEqual(allowed.returncode, 0)
            authorized = subprocess.run(
                [str(guard), "--session", "ipse", "agent", "start", "w"],
                check=False,
                env={**env, "IPSE_HERDR_DISPATCH": "1"},
            )
            self.assertEqual(authorized.returncode, 0)

    def test_hermes_session_audit_detects_raw_bypass_and_total_budget(self) -> None:
        audit = SCRIPT.with_name("audit_hermes_session.py")
        session = "session-raw"
        lines = [
            f"2026-01-01 00:00:00,000 INFO [{session}] agent.turn_context: conversation turn:",
            f"2026-01-01 00:00:01,000 INFO [{session}] agent.conversation_loop: API call #1: model=x in=500001 out=1",
            f"2026-01-01 00:00:02,000 INFO [{session}] agent.tool_executor: herdr --session ipse agent start worker",
        ]
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "agent.log"
            log.write_text("\n".join(lines), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(audit), str(log), "--session", session, "--orchestrated"],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("input_tokens=500001>400000", result.stdout)
        self.assertIn("raw_herdr_mutations=1>0", result.stdout)

    def test_hermes_session_audit_rejects_captain_loops_and_writes(self) -> None:
        audit = SCRIPT.with_name("audit_hermes_session.py")
        session = "session-1"
        lines = [f"INFO [{session}] agent.turn_context: conversation turn:"]
        lines.extend(
            f"INFO [{session}] agent.conversation_loop: API call #{index}: model=x in=1000 out=10"
            for index in range(1, 10)
        )
        lines.append(f"INFO [{session}] agent.tool_executor: tool patch completed")
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "agent.log"
            log.write_text("\n".join(lines) + "\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(audit), str(log), "--session", session, "--orchestrated"],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("max_calls_per_turn=9>8", result.stdout)
        self.assertIn("captain_write_calls=1>0", result.stdout)


if __name__ == "__main__":
    unittest.main()
