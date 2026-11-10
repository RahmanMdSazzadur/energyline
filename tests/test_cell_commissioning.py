import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/api"))
from server import ExperimentService, ConflictError


class CommissioningSuiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = ExperimentService(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_suite_persistence_and_all_case_evidence(self):
        report = self.service.commission({})
        self.assertTrue(report["passed"])
        self.assertEqual(report["passed_cases"], 11)
        self.assertEqual(report, self.service.get_commissioning(report["id"]))
        self.assertEqual(
            report, ExperimentService(self.temp.name).get_commissioning(report["id"])
        )
        for case in report["cases"]:
            trace_id = case["evidence_url"].rsplit("/", 1)[-1]
            trace = json.loads(
                (Path(self.temp.name) / "cell" / f"{trace_id}.json").read_text()
            )
            self.assertEqual(trace["suite_id"], report["id"])
            self.assertEqual(trace["demo"], case["demo"])
            self.assertTrue(trace["passed"])

    def test_retry_reuses_report_and_traces(self):
        first = self.service.commission({"request_id": "suite-repeat-001"})
        second = self.service.commission({"request_id": "suite-repeat-001"})
        self.assertEqual(first, second)
        self.assertEqual(len(list((Path(self.temp.name) / "cell").glob("*.json"))), 11)

    def test_failure_is_retained_and_other_cases_continue(self):
        from server import run_demo

        def fake(name):
            if name == "clamp_timeout":
                raise RuntimeError("injected commissioning test error")
            result = run_demo(name)
            if name == "process_timeout":
                result["checks"]["expected_fault"] = False
                result["passed"] = False
            return result

        with patch("server.run_demo", side_effect=fake):
            report = self.service.commission({})
        self.assertFalse(report["passed"])
        self.assertEqual(report["failed_cases"], 2)
        self.assertEqual(len(report["cases"]), 11)
        self.assertIn(
            "error", next(c for c in report["cases"] if c["demo"] == "clamp_timeout")
        )
        self.assertFalse(
            next(c for c in report["cases"] if c["demo"] == "process_timeout")["passed"]
        )

    def test_changed_model_cannot_reuse_request_id(self):
        self.service.commission({"request_id": "changed-model-001"})
        with patch("server.hashlib.sha256") as sha:
            sha.return_value.hexdigest.return_value = "changed-model-hash"
            with self.assertRaises(ConflictError):
                self.service.commission({"request_id": "changed-model-001"})

    def test_invalid_request_and_unknown_report(self):
        for request in (
            [],
            {"demo": "normal"},
            {"request_id": "bad"},
            {"request_id": True},
        ):
            with self.assertRaises(ValueError):
                self.service.commission(request)
        self.assertIsNone(self.service.get_commissioning("not-found"))


if __name__ == "__main__":
    unittest.main()
