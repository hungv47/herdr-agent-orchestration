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
        with self.assertRaisesRegex(ValueError, "no blank lines"):
            self.dispatch.parse_brief(valid.replace("write=", "\nwrite="))
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

    def test_visible_output_limit_is_deterministic(self) -> None:
        reached = self.watcher.output_limit_reached
        self.assertFalse(reached(19_999, 20_000))
        self.assertTrue(reached(20_000, 20_000))

    def test_visible_output_is_counted_across_rolling_windows(self) -> None:
        delta = self.watcher.visible_output_delta
        first = "a\nb\nc\n"
        second = "b\nc\nd\n"
        third = "c\nd\ne\n"
        total = delta("", first)
        self.assertEqual(delta(first, second), len("d\n"))
        total += delta(first, second) or 0
        total += delta(second, third) or 0
        self.assertEqual(total, len(first) + len("d\n") + len("e\n"))
        self.assertIsNone(delta(first, "unrelated\nwindow\n"))
        self.assertEqual(delta(first, ""), 0)

    def test_retained_output_reaches_cap_even_for_repeated_one_character_lines(self) -> None:
        line_count = self.watcher.retained_output_lines(20_000)
        repeated = "x\n" * line_count
        self.assertEqual(line_count, 20_001)
        self.assertGreater(line_count, 400)
        self.assertTrue(
            self.watcher.output_limit_reached(
                self.watcher.visible_output_delta("", repeated),
                20_000,
            )
        )

    def test_status_reads_real_nested_herdr_payload(self) -> None:
        payload = {"result": {"agent": {"agent_status": "working"}, "type": "agent_info"}}
        self.assertEqual(self.watcher.parse_status(payload), "working")
        self.assertEqual(self.watcher.parse_status({"agent_status": "done"}), "done")
        self.assertEqual(self.watcher.parse_status({}), "unknown")

    def test_worker_prompt_adds_caveman_without_an_extra_line(self) -> None:
        brief = "\n".join(
            (
                "role=worker; outcome=one result",
                "write=src/result.py",
                "non-goals=no delegation",
                "accept=python3 -m unittest",
                "return=accepted|blocked: paths=<paths>; checks=<checks>; blocker=<blocker>; then stop",
            )
        )
        prompt = self.dispatch.caveman_worker_prompt(brief)
        self.assertEqual(len(prompt.splitlines()), 5)
        self.assertIn(self.dispatch.CAVEMAN_SENTINEL, prompt.splitlines()[-1])
        self.assertLessEqual(len(prompt), self.dispatch.PROMPT_LIMIT)

    def test_worker_prompt_limit_includes_caveman_suffix(self) -> None:
        brief = "\n".join(
            (
                f"role=worker; outcome={'x' * 650}",
                "write=src/result.py",
                "non-goals=no delegation",
                "accept=python3 -m unittest",
                "return=accepted|blocked: paths=<paths>; checks=<checks>; blocker=<blocker>; then stop",
            )
        )
        self.dispatch.parse_brief(brief)
        with self.assertRaisesRegex(ValueError, "worker prompt exceeds 1,200"):
            self.dispatch.caveman_worker_prompt(brief)

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

    def test_worker_start_retries_a_new_pane_until_its_shell_is_ready(self) -> None:
        busy = subprocess.CompletedProcess(
            ["herdr"],
            1,
            stdout="",
            stderr='{"error":{"code":"agent_pane_busy"}}',
        )
        ready = subprocess.CompletedProcess(["herdr"], 0, stdout="{}", stderr="")
        route = self.dispatch.Route("opencode", ("-m", "model"))
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
            sentinel_only = "\n".join(self.dispatch.POLICY_SENTINELS)
            policy = sentinel_only + "\n" + ("complete bounded policy rule\n" * 100)
            opencode = home / ".config/opencode/AGENTS.md"
            opencode.parent.mkdir(parents=True)
            opencode.write_text(policy, encoding="utf-8")
            cline = home / ".agents/AGENTS.md"
            cline.parent.mkdir(parents=True)
            cline.write_text(policy, encoding="utf-8")
            pi = home / ".pi/agent/AGENTS.md"
            pi.parent.mkdir(parents=True)
            pi.write_text(policy, encoding="utf-8")
            with mock.patch.object(self.dispatch.Path, "home", return_value=home):
                self.dispatch.verify_route_config(self.dispatch.build_route("opencode"))
                self.dispatch.verify_route_config(self.dispatch.build_route("cline"))
                self.dispatch.verify_route_config(self.dispatch.build_route("pi"))
                cline.write_text(sentinel_only, encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "policy is unavailable or stale"):
                    self.dispatch.verify_route_config(self.dispatch.build_route("cline"))
                stale = policy.replace("ipse-orchestration/v9", "ipse-orchestration/v8")
                cline.write_text(stale, encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "policy is unavailable or stale"):
                    self.dispatch.verify_route_config(self.dispatch.build_route("cline"))
                cline.write_text(self.dispatch.CAVEMAN_SENTINEL, encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "policy is unavailable or stale"):
                    self.dispatch.verify_route_config(self.dispatch.build_route("cline"))
                opencode.write_text("{}", encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "policy is unavailable or stale"):
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
            workspace = subprocess.run(
                [str(guard), "workspace", "list"],
                check=False,
                env=env,
            )
            self.assertEqual(workspace.returncode, 0)
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

    def test_hermes_session_audit_allows_multiple_bounded_turns(self) -> None:
        audit = SCRIPT.with_name("audit_hermes_session.py")
        session = "session-2"
        lines = []
        for _turn in range(2):
            lines.append(f"INFO [{session}] agent.turn_context: conversation turn:")
            lines.extend(
                f"INFO [{session}] agent.conversation_loop: API call #{index}: model=x in=100 out=10"
                for index in range(1, 5)
            )
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "agent.log"
            log.write_text("\n".join(lines) + "\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(audit), str(log), "--session", session],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_hermes_session_audit_rejects_missing_session(self) -> None:
        audit = SCRIPT.with_name("audit_hermes_session.py")
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "agent.log"
            log.write_text("other session\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(audit), str(log), "--session", "missing"],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("session_not_found_or_empty", result.stdout)


if __name__ == "__main__":
    unittest.main()
