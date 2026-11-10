"""Hosted-demo behavior: ephemeral storage configuration, notices and bounded work."""

import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/api"))
from server import ExperimentService, handler_for, execute_job


class HostedDemoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = ExperimentService(self.temp.name)
        self.started = threading.Event()
        self.release = threading.Event()
        self.server = None

    def tearDown(self):
        self.release.set()
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=5)
        self.temp.cleanup()

    def start(self, public=True, **options):
        with patch.dict(
            os.environ,
            {
                "ENERGYLINE_PUBLIC_DEMO": "1" if public else "0",
                "ENERGYLINE_RELEASE_URL": "https://github.com/RahmanMdSazzadur/energyline/releases/download/v1.1.1/EnergyLine-v1.1.1-final.zip",
            },
        ):
            self.server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                handler_for(self.service, **{"runner": execute_job, **options}),
            )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def request(self, path, body=None, origin=None):
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=10
        )
        headers = {}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if origin:
            headers["Origin"] = origin
        conn.request("POST" if body is not None else "GET", path, body, headers)
        response = conn.getresponse()
        data = response.read()
        result = response.status, dict(response.getheaders()), data
        conn.close()
        return result

    def test_environment_selects_runtime_storage(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(
            os.environ, {"ENERGYLINE_DATA_DIR": d}
        ):
            service = ExperimentService()
            self.assertEqual(service.directory, Path(d))
            self.assertTrue(service.database.exists())

    def test_hosted_page_discloses_shared_temporary_runs(self):
        self.start()
        status, _, data = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b"experiments are shared and temporary", data)
        status, _, data = self.request("/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(data)["public_demo"])

    def test_local_page_keeps_existing_behavior(self):
        self.start(public=False)
        _, _, data = self.request("/")
        self.assertNotIn(b"experiments are shared and temporary", data)

    def test_release_redirect_uses_canonical_asset(self):
        self.start()
        status, headers, data = self.request("/downloads/release.zip")
        self.assertEqual(status, 302)
        self.assertTrue(
            headers["Location"].startswith(
                "https://github.com/RahmanMdSazzadur/energyline/releases/download/"
            )
        )
        self.assertEqual(data, b"")

    def test_second_compute_request_receives_retry_response(self):
        def slow_run(_request):
            self.started.set()
            if not self.release.wait(timeout=5):
                raise RuntimeError("Test timed out")
            return {"completed": True}

        self.service.run = slow_run
        self.start()
        first = []
        worker = threading.Thread(
            target=lambda: first.append(self.request("/api/experiments", "{}"))
        )
        worker.start()
        self.assertTrue(self.started.wait(timeout=3))
        status, _, data = self.request("/api/cell/commission", "{}")
        self.assertEqual(status, 429)
        self.assertIn("another job", json.loads(data)["error"])
        self.release.set()
        worker.join(timeout=5)
        self.assertEqual(first[0][0], 200)
        self.assertEqual(self.request("/api/experiments", "{}")[0], 200)

    def test_invalid_request_does_not_keep_compute_slot(self):
        self.start()
        self.assertEqual(self.request("/api/experiments", "{")[0], 400)
        self.assertEqual(
            self.request("/api/cell/demo", json.dumps({"demo": "normal"}))[0], 200
        )
