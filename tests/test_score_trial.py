import copy
import hashlib
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
    sha = lambda value: hashlib.sha256(value.encode()).hexdigest()
    runs = []
    for index in range(5):
        runs.append(
            {
                "name": f"case-{index + 1}",
                "model": "deepseek-v4-flash",
                "starting_commit": "a" * 40,
                "accept_command": "python3 -m unittest",
                "accept_command_sha256": sha("python3 -m unittest"),
                "task_brief_sha256": sha(f"case-{index + 1}-brief"),
                "config_sha256_before": sha("same-config"),
                "config_sha256_after": sha("same-config"),
                "token_source": "provider_receipt",
                "baseline": {
                    "accept_exit": 0,
                    "uncached_input_tokens": 10_000,
                    "output_tokens": 500,
                    "wall_seconds": 100,
                    "worker_prompts": 1,
                    "retries": 0,
                    "token_receipt_sha256": sha(f"baseline-receipt-{index}"),
                },
                "candidate": {
                    "accept_exit": 0,
                    "uncached_input_tokens": 7_500,
                    "output_tokens": 450,
                    "wall_seconds": 105,
                    "worker_prompts": 1,
                    "retries": 0,
                    "token_receipt_sha256": sha(f"candidate-receipt-{index}"),
                },
            }
        )
    return {
        "headroom_version": "0.34.0",
        "route": "opencode",
        "concurrency_survives_owner_exit": True,
        "concurrency_receipt_sha256": sha("concurrency-drill"),
        "direct_bypass_after_proxy_stop": True,
        "direct_bypass_receipt_sha256": sha("bypass-drill"),
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
        self.assertEqual(report["metrics"]["output_regression_pct"], -10.0)
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
        payload["runs"][0]["config_sha256_after"] = "b" * 64

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
        self.assertIn("case-1: candidate worker prompt count is not one", report["failures"])
        self.assertIn("case-2: candidate retry count is not zero", report["failures"])
        self.assertIn("case-3: baseline worker prompt count is not one", report["failures"])
        self.assertIn("case-4: baseline retry count is not zero", report["failures"])

    def test_rejects_zero_fractional_or_boolean_counts(self):
        for value in (0, 0.5, True):
            with self.subTest(value=value):
                payload = passing_payload()
                payload["runs"][0]["candidate"]["worker_prompts"] = value
                report = self.score.evaluate(payload)
                self.assertFalse(report["adopt"])

    def test_rejects_non_finite_metrics(self):
        for value in (float("nan"), float("inf")):
            with self.subTest(value=value):
                payload = passing_payload()
                payload["runs"][0]["candidate"]["uncached_input_tokens"] = value
                report = self.score.evaluate(payload)
                self.assertFalse(report["adopt"])
                self.assertTrue(any("finite" in item for item in report["failures"]))

    def test_json_parser_rejects_non_finite_constants(self):
        with self.assertRaises(ValueError):
            __import__("json").loads("{\"value\": NaN}", parse_constant=self.score.reject_json_constant)

    def test_rejects_output_token_regression(self):
        payload = passing_payload()
        for run in payload["runs"]:
            run["candidate"]["output_tokens"] = 600

        report = self.score.evaluate(payload)

        self.assertIn("output-token regression above 10%", report["failures"])

    def test_rejects_unverifiable_or_incomparable_evidence(self):
        mutations = (
            (lambda p: p["runs"][0].update(model=""), "case-1: model is missing"),
            (lambda p: p["runs"][0].update(starting_commit="not-a-commit"), "case-1: starting commit is invalid"),
            (lambda p: p["runs"][0].update(task_brief_sha256="not-a-hash"), "case-1: task brief digest is invalid"),
            (lambda p: p["runs"][0].update(accept_command="different"), "case-1: acceptance command digest does not match"),
            (lambda p: p["runs"][0].update(token_source="headroom_estimate"), "case-1: token source must be a provider or harness receipt"),
            (lambda p: p["runs"][0]["baseline"].update(token_receipt_sha256="fake"), "case-1: baseline token receipt digest is invalid"),
        )
        for mutate, expected in mutations:
            with self.subTest(expected=expected):
                payload = passing_payload()
                mutate(payload)
                self.assertIn(expected, self.score.evaluate(payload)["failures"])

    def test_requires_complete_measured_evidence(self):
        payload = passing_payload()
        payload["runs"][0]["config_sha256_before"] = ""
        payload["runs"][0]["config_sha256_after"] = ""
        payload["runs"][1]["candidate"].pop("output_tokens")
        payload["runs"][2] = "not-an-object"

        report = self.score.evaluate(payload)

        self.assertFalse(report["adopt"])
        self.assertIn("case-1: configuration hashes are invalid", report["failures"])
        self.assertTrue(
            any(failure.startswith("case-2: invalid metrics:") for failure in report["failures"])
        )
        self.assertIn("run-3: run must be an object", report["failures"])

    def test_malformed_shared_or_side_fields_fail_closed(self):
        payload = passing_payload()
        payload["runs"][0]["accept_command"] = ["not", "text"]
        payload["runs"][1]["baseline"] = ["not", "an", "object"]

        report = self.score.evaluate(payload)

        self.assertFalse(report["adopt"])
        self.assertIn("case-1: acceptance command is missing", report["failures"])
        self.assertIn("case-2: baseline token receipt digest is invalid", report["failures"])

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
            (
                "concurrency_receipt_sha256",
                "bad",
                "concurrency drill receipt digest is invalid",
            ),
            (
                "direct_bypass_receipt_sha256",
                "bad",
                "direct-bypass drill receipt digest is invalid",
            ),
        ):
            with self.subTest(field=field):
                payload = copy.deepcopy(passing_payload())
                payload[field] = value
                report = self.score.evaluate(payload)
                self.assertIn(expected, report["failures"])


if __name__ == "__main__":
    unittest.main()
