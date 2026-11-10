import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/api"))
from server import ExperimentService, ConflictError


class ExperimentAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = ExperimentService(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_persistence_and_trace(self):
        result = self.service.run(
            {
                "scenario": "quality_rework",
                "replications": 2,
                "request_id": "test-request-001",
            }
        )
        self.assertEqual(result["aggregate"]["replications"], 2)
        self.assertEqual(result, self.service.get(result["id"]))
        other = ExperimentService(self.temp.name)
        self.assertEqual(other.list()[0]["id"], result["id"])
        folder = Path(self.temp.name) / result["id"]
        self.assertTrue((folder / "first_run_events.csv").exists())
        manifest = json.loads((folder / "manifest.json").read_text())
        self.assertEqual(manifest["seeds"], [20261109, 20261110])
        self.assertTrue(manifest["source_sha256"])
        for run in result["runs"]:
            self.assertEqual(
                run["released_units"],
                run["accepted_units"] + run["scrapped_units"] + run["unfinished_units"],
            )

    def test_idempotency_and_conflict(self):
        request = {
            "scenario": "manual",
            "replications": 1,
            "request_id": "repeat-this-001",
        }
        first = self.service.run(request)
        self.assertEqual(first, self.service.run(request))
        self.assertEqual(len(self.service.list()), 1)
        with self.assertRaises(ConflictError):
            self.service.run(dict(request, operators=2))

    def test_validation(self):
        for request in [
            {"replications": 101},
            {"operators": 0},
            {"operators": True},
            {"scenario": "../../README.md"},
            {"request_id": "bad"},
            {"seed": -1},
            {"target": 0},
            {"unknown": 1},
            [],
            {"scenario": []},
        ]:
            with self.assertRaises(ValueError):
                self.service.run(request)
        self.assertEqual(self.service.list(), [])

    def test_same_inputs_same_simulated_output(self):
        first = self.service.run({"scenario": "manual", "replications": 1})
        second = self.service.run({"scenario": "manual", "replications": 1})
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(first["aggregate"], second["aggregate"])


class HTTPBoundaryTests(unittest.TestCase):
    def setUp(self):
        import threading
        from http.server import ThreadingHTTPServer
        from server import handler_for

        self.temp = tempfile.TemporaryDirectory()
        self.service = ExperimentService(self.temp.name)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(self.service))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, path, body=None, headers=None):
        import urllib.request
        import urllib.error

        request = urllib.request.Request(
            self.url + path, data=body, headers=headers or {}
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            with error:
                return error.code, error.read()

    def test_http_roundtrip_and_artifact(self):
        status, _ = self.request("/api/health")
        self.assertEqual(status, 200)
        status, data = self.request(
            "/api/experiments",
            json.dumps({"scenario": "manual", "replications": 1}).encode(),
            {"Content-Type": "application/json"},
        )
        self.assertEqual(status, 200)
        result = json.loads(data)
        status, data = self.request(result["artifacts"]["first_run_events"])
        self.assertEqual(status, 200)
        self.assertIn(b"unit_id", data)
        self.assertEqual(self.request("/../../README.md")[0], 404)

    def test_http_rejects_bad_and_cross_origin_requests(self):
        self.assertEqual(self.request("/api/experiments", b"{}")[0], 415)
        self.assertEqual(
            self.request(
                "/api/experiments", b"{", {"Content-Type": "application/json"}
            )[0],
            400,
        )
        self.assertEqual(
            self.request(
                "/api/experiments",
                b"{}",
                {"Content-Type": "application/json", "Origin": "https://example.com"},
            )[0],
            403,
        )
        self.assertEqual(self.service.list(), [])

    def test_cell_demonstration_api_and_saved_trace(self):
        status, data = self.request("/api/cell/demos")
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(data)), 11)
        status, data = self.request(
            "/api/cell/demo",
            json.dumps({"demo": "permit_removed"}).encode(),
            {"Content-Type": "application/json"},
        )
        self.assertEqual(status, 200)
        result = json.loads(data)
        self.assertTrue(result["passed"])
        self.assertEqual(result["expected_fault"], "PERMIT_REMOVED")
        status, data = self.request(result["artifact"])
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data), result)
        status, data = self.request("/cell")
        self.assertEqual(status, 200)
        self.assertIn(b"Virtual S3 cell", data)

    def test_cell_unknown_demo_and_extra_fields_rejected(self):
        for payload in (
            {"demo": "unknown"},
            {"demo": "normal", "commands": []},
            {"demo": []},
        ):
            status, _ = self.request(
                "/api/cell/demo",
                json.dumps(payload).encode(),
                {"Content-Type": "application/json"},
            )
            self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
