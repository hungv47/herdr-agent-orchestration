import copy
import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "evals" / "score_trial.py"


def load_module():
    spec = importlib.util.spec_from_file_location("score_trial", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def passing_payload():
    runs = []
    for index in range(5):
        runs.append(
            {
                "name": f"case-{index + 1}",
                "accept_command": "python3 -m unittest",
                "config_sha256_before": "same-hash",
                "config_sha256_after": "same-hash",
                "token_source": "provider receipt",
                "baseline": {
                    "accept_exit": 0,
                    "uncached_input_tokens": 10_000,
                    "output_tokens": 500,
                    "wall_seconds": 100,
                    "worker_prompts": 1,
                    "retries": 0,
                },
                "candidate": {
                    "accept_exit": 0,
                    "uncached_input_tokens": 7_500,
                    "output_tokens": 450,
                    "wall_seconds": 105,
                    "worker_prompts": 1,
                    "retries": 0,
                },
            }
        )
    return {
        "headroom_version": "0.34.0",
        "route": "opencode",
        "concurrency_survives_owner_exit": True,
        "direct_bypass_after_proxy_stop": True,
        "runs": runs,
    }


class TrialScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.score = load_module()

    def test_passing_trial_is_adoptable(self):
        report = self.score.evaluate(passing_payload())

        self.assertTrue(report["adopt"])
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["metrics"]["uncached_input_savings_pct"], 25.0)
        self.assertEqual(report["metrics"]["wall_regression_pct"], 5.0)

    def test_requires_five_representative_runs(self):
        payload = passing_payload()
        payload["runs"] = payload["runs"][:4]

        report = self.score.evaluate(payload)

        self.assertFalse(report["adopt"])
        self.assertIn("at least 5 runs", report["failures"])

    def test_rejects_any_correctness_regression(self):
        payload = passing_payload()
        payload["runs"][2]["candidate"]["accept_exit"] = 1

        report = self.score.evaluate(payload)

        self.assertFalse(report["adopt"])
        self.assertIn("case-3: candidate acceptance failed", report["failures"])

    def test_rejects_less_than_twenty_percent_input_savings(self):
        payload = passing_payload()
        for run in payload["runs"]:
            run["candidate"]["uncached_input_tokens"] = 8_500

        report = self.score.evaluate(payload)

        self.assertFalse(report["adopt"])
        self.assertIn("uncached input savings below 20%", report["failures"])

    def test_rejects_more_than_ten_percent_wall_regression(self):
        payload = passing_payload()
        for run in payload["runs"]:
            run["candidate"]["wall_seconds"] = 111

        report = self.score.evaluate(payload)

        self.assertFalse(report["adopt"])
        self.assertIn("wall-time regression above 10%", report["failures"])

    def test_rejects_persistent_config_mutation(self):
        payload = passing_payload()
        payload["runs"][0]["config_sha256_after"] = "changed"

        report = self.score.evaluate(payload)

        self.assertFalse(report["adopt"])
        self.assertIn("case-1: persistent config changed", report["failures"])

    def test_rejects_prompt_or_retry_loops(self):
        payload = passing_payload()
        payload["runs"][0]["candidate"]["worker_prompts"] = 2
        payload["runs"][1]["candidate"]["retries"] = 1
        payload["runs"][2]["baseline"]["worker_prompts"] = 2
        payload["runs"][3]["baseline"]["retries"] = 1

        report = self.score.evaluate(payload)

        self.assertFalse(report["adopt"])
        self.assertIn("case-1: candidate used more than one worker prompt", report["failures"])
        self.assertIn("case-2: candidate retried", report["failures"])
        self.assertIn("case-3: baseline used more than one worker prompt", report["failures"])
        self.assertIn("case-4: baseline retried", report["failures"])

    def test_requires_complete_measured_evidence(self):
        payload = passing_payload()
        payload["runs"][0]["config_sha256_before"] = ""
        payload["runs"][0]["config_sha256_after"] = ""
        payload["runs"][1]["candidate"].pop("output_tokens")
        payload["runs"][2] = "not-an-object"

        report = self.score.evaluate(payload)

        self.assertFalse(report["adopt"])
        self.assertIn("case-1: configuration hashes are missing", report["failures"])
        self.assertTrue(
            any(failure.startswith("case-2: invalid metrics:") for failure in report["failures"])
        )
        self.assertIn("run-3: run must be an object", report["failures"])

    def test_rejects_global_or_unsafe_route(self):
        for field, value, expected in (
            ("route", "codex", "trial route must be opencode"),
            (
                "concurrency_survives_owner_exit",
                False,
                "concurrent-session survival not proven",
            ),
            (
                "direct_bypass_after_proxy_stop",
                False,
                "direct bypass after proxy failure not proven",
            ),
        ):
            with self.subTest(field=field):
                payload = copy.deepcopy(passing_payload())
                payload[field] = value
                report = self.score.evaluate(payload)
                self.assertIn(expected, report["failures"])


if __name__ == "__main__":
    unittest.main()
