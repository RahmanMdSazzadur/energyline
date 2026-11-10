"""Exercise public limits through HTTP, real worker processes and saved evidence."""

import concurrent.futures
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/api"))
from public_limits import (
    JobBudget,
    BoundedHTTPServer,
    run_isolated,
    prune_public_results,
    WorkerConflictError,
    read_public_body,
)
from server import ExperimentService, execute_job
import test_hosting


class BudgetTests(unittest.TestCase):
    def test_shared_sliding_windows_and_recovery(self):
        clock = [0]
        budget = JobBudget(windows=((60, 2), (3600, 3)), clock=lambda: clock[0])
        self.assertEqual([budget.reserve() for _ in range(3)], [0, 0, 60])
        clock[0] = 60
        self.assertEqual(budget.reserve(), 0)
        self.assertEqual(budget.reserve(), 3540)
        clock[0] = 3600
        self.assertEqual(budget.reserve(), 0)

    def test_concurrent_reservations_cannot_exceed_budget(self):
        budget = JobBudget()
        with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:
            results = list(pool.map(lambda _: budget.reserve(), range(40)))
        self.assertEqual(results.count(0), 10)
        self.assertEqual(len(budget.starts), 10)


class PublicHTTPTests(unittest.TestCase):
    setUp = test_hosting.HostedDemoTests.setUp
    tearDown = test_hosting.HostedDemoTests.tearDown
    start = test_hosting.HostedDemoTests.start
    request = test_hosting.HostedDemoTests.request

    def test_budget_is_shared_across_routes_and_returns_retry_header(self):
        clock = [0]
        budget = JobBudget(windows=((60, 2),), clock=lambda: clock[0])
        self.start(budget=budget, runner=lambda *_: {"ok": True})
        self.assertEqual(self.request("/api/experiments", "{}")[0], 200)
        self.assertEqual(self.request("/api/cell/demo", '{"demo":"normal"}')[0], 200)
        status, headers, data = self.request("/api/cell/commission", "{}")
        self.assertEqual(status, 429)
        self.assertEqual(headers["Retry-After"], "60")
        self.assertEqual(json.loads(data)["retry_after_seconds"], 60)
        self.assertEqual(self.request("/api/health")[0], 200)
        clock[0] = 60
        self.assertEqual(self.request("/api/cell/commission", "{}")[0], 200)

    def test_public_shift_cap_and_html_match(self):
        self.start()
        status, _, data = self.request("/api/experiments", '{"replications":31}')
        self.assertEqual(status, 400)
        self.assertIn("30 shifts", json.loads(data)["error"])
        self.assertIn(
            b'id="replications" type="number" min="1" max="30"', self.request("/")[2]
        )
        self.assertEqual(self.service.list(), [])
        # The local engine still permits larger studies.
        self.assertEqual(
            self.service.prepare({"replications": 100})[0]["replications"], 100
        )

    def test_timeout_response_releases_slot(self):
        def timed_out(*_):
            raise subprocess.TimeoutExpired("simulation", 30)

        self.start(runner=timed_out)
        self.assertEqual(self.request("/api/experiments", "{}")[0], 504)
        # A second attempt is not stuck behind the previous job.
        self.assertEqual(self.request("/api/experiments", "{}")[0], 504)
        self.assertEqual(self.request("/api/health")[0], 200)

    def test_real_isolated_http_worker_saves_results_and_validates_input(self):
        self.start(runner=run_isolated)
        status, _, body = self.request(
            "/api/experiments",
            '{"scenario":"manual","replications":1,"request_id":"worker-http-001"}',
        )
        self.assertEqual(status, 200)
        run = json.loads(body)
        self.assertEqual(self.request(run["artifacts"]["result"])[0], 200)
        self.assertEqual(self.request(run["artifacts"]["first_run_events"])[0], 200)
        status, _, _ = self.request(
            "/api/experiments",
            '{"scenario":"manual","replications":1,"operators":2,"request_id":"worker-http-001"}',
        )
        self.assertEqual(status, 409)
        self.assertEqual(self.request("/api/cell/commission", "[]")[0], 400)
        status, _, body = self.request("/api/cell/commission", "{}")
        self.assertEqual(status, 200)
        suite = json.loads(body)
        self.assertTrue(suite["passed"])
        self.assertEqual(self.request(suite["cases"][0]["evidence_url"])[0], 200)


class WorkerAndRetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = ExperimentService(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_hard_deadline_kills_worker_and_next_job_succeeds(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            run_isolated(
                self.service, "/api/experiments", {"replications": 30}, timeout=0.001
            )
        prune_public_results(self.temp.name)
        self.assertEqual(self.service.list(), [])
        result = run_isolated(self.service, "/api/cell/demo", {"demo": "normal"})
        self.assertTrue(result["passed"])

    def test_count_and_age_pruning_delete_rows_and_artifacts_together(self):
        runs = [
            self.service.run({"scenario": "manual", "replications": 1})
            for _ in range(3)
        ]
        prune_public_results(self.temp.name, max_runs=1)
        self.assertEqual([r["id"] for r in self.service.list()], [runs[-1]["id"]])
        self.assertFalse((Path(self.temp.name) / runs[0]["id"]).exists())
        prune_public_results(
            self.temp.name, now=datetime.now(timezone.utc).timestamp() + 86401
        )
        self.assertEqual(self.service.list(), [])

    def test_trace_eviction_invalidates_suite_and_storage_is_bounded(self):
        report = self.service.commission({})
        prune_public_results(self.temp.name, max_traces=1)
        self.assertIsNone(self.service.get_commissioning(report["id"]))
        self.assertEqual(list((Path(self.temp.name) / "cell").glob("*.json")), [])
        self.service.run({"scenario": "manual", "replications": 1})
        prune_public_results(self.temp.name, max_bytes=1)
        self.assertEqual(self.service.list(), [])

    def test_orphaned_worker_files_removed_without_touching_external_files(self):
        root = Path(self.temp.name)
        orphan = root / "00000000-0000-0000-0000-000000000000"
        orphan.mkdir()
        (orphan / "partial.csv").write_text("partial")
        with tempfile.TemporaryDirectory() as external:
            target = Path(external) / "private.txt"
            target.write_text("untouched")
            (root / "outside").symlink_to(external, target_is_directory=True)
            prune_public_results(root)
            self.assertEqual(target.read_text(), "untouched")
        self.assertFalse(orphan.exists())


class UploadTests(unittest.TestCase):
    def test_partial_chunks_cannot_extend_total_upload_deadline(self):
        connection = Mock()
        stream = Mock()
        stream.read1.return_value = b"x"
        clock = Mock(side_effect=[0, 3, 6, 11])
        with self.assertRaises(TimeoutError):
            read_public_body(stream, connection, 4, timeout=10, clock=clock)
        self.assertEqual(stream.read1.call_count, 2)
        self.assertEqual(
            [call.args[0] for call in connection.settimeout.call_args_list], [7, 4]
        )

    def test_disconnected_upload_is_rejected(self):
        with self.assertRaises(ValueError):
            read_public_body(Mock(read1=Mock(return_value=b"")), Mock(), 2)


class ConnectionTests(unittest.TestCase):
    def test_excess_connections_do_not_start_more_handler_threads(self):
        entered, release = threading.Event(), threading.Event()

        class HeldHandler:
            def __init__(self, *_):
                entered.set()
                release.wait(3)

        server = BoundedHTTPServer(("127.0.0.1", 0), HeldHandler, max_connections=1)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        first = socket.create_connection(server.server_address, timeout=2)
        try:
            self.assertTrue(entered.wait(2))
            with socket.create_connection(server.server_address, timeout=2) as second:
                self.assertEqual(second.recv(1), b"")
        finally:
            release.set()
            first.close()
            server.shutdown()
            server.server_close()
            thread.join(3)
