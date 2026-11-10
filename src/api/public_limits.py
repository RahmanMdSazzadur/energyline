"""Bounds for the single-instance, anonymous public demonstration."""

from collections import deque
from contextlib import closing
from datetime import datetime
from http.server import ThreadingHTTPServer
import json
import math
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time

MAX_SHIFTS = 30
JOB_TIMEOUT = 30
REQUEST_TIMEOUT = 10
MAX_CONNECTIONS = 24
UUID = re.compile(r"[0-9a-f-]{36}")


class WorkerConflictError(ValueError):
    pass


class JobBudget:
    """Shared sliding windows; no client addresses or cookies are stored."""

    def __init__(self, windows=((60, 10), (3600, 60)), clock=time.monotonic):
        self.windows, self.clock = windows, clock
        self.starts = deque()
        self.lock = threading.Lock()

    def reserve(self):
        with self.lock:
            now = self.clock()
            while self.starts and self.starts[0] <= now - max(
                w[0] for w in self.windows
            ):
                self.starts.popleft()
            waits = []
            for seconds, limit in self.windows:
                recent = [t for t in self.starts if t > now - seconds]
                if len(recent) >= limit:
                    waits.append(recent[-limit] + seconds - now)
            if waits:
                return max(1, math.ceil(max(waits)))
            self.starts.append(now)
            return 0


class BoundedHTTPServer(ThreadingHTTPServer):
    """Reject excess connections before allocating another handler thread."""

    daemon_threads = True
    request_queue_size = MAX_CONNECTIONS

    def __init__(self, *args, max_connections=MAX_CONNECTIONS, **kwargs):
        self.slots = threading.BoundedSemaphore(max_connections)
        super().__init__(*args, **kwargs)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


def read_public_body(
    stream, connection, length, *, timeout=REQUEST_TIMEOUT, clock=time.monotonic
):
    """Use one total upload deadline, including clients sending tiny chunks."""
    deadline = clock() + timeout
    data = bytearray()
    while len(data) < length:
        remaining = deadline - clock()
        if remaining <= 0:
            raise TimeoutError("Upload deadline exceeded")
        connection.settimeout(remaining)
        chunk = stream.read1(length - len(data))
        if not chunk:
            raise ValueError("Incomplete request body")
        data.extend(chunk)
    connection.settimeout(REQUEST_TIMEOUT)
    return bytes(data)


def run_isolated(service, path, request, timeout=JOB_TIMEOUT):
    """Kill and reap a timed-out child before releasing the compute slot."""
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("server.py")),
            "--public-job",
            path,
            "--data-dir",
            str(service.directory),
        ],
        input=json.dumps(request),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=timeout,
        check=True,
    )
    envelope = json.loads(completed.stdout)
    if envelope["status"] == "conflict":
        raise WorkerConflictError(envelope["error"])
    if envelope["status"] == "invalid":
        raise ValueError(envelope["error"])
    if envelope["status"] != "ok":
        raise RuntimeError("Public worker failed")
    return envelope["result"]


def prune_public_results(
    directory,
    *,
    now=None,
    max_runs=50,
    max_suites=20,
    max_traces=250,
    max_bytes=80 * 1024 * 1024,
    max_age=86400,
):
    """Prune generated files/rows only, while the compute slot is held.

    Expired/evicted artifacts invalidate their DB records. Project files are
    outside this dedicated runtime directory. Symlinks are never followed.
    """
    directory = Path(directory)
    now = time.time() if now is None else now
    db_path = directory / "experiments.sqlite3"
    changed = False
    with closing(sqlite3.connect(db_path)) as db:

        def remove_run(run_id):
            nonlocal changed
            path = directory / run_id
            if UUID.fullmatch(run_id) and path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            db.execute("DELETE FROM experiments WHERE id=?", (run_id,))
            changed = True

        def remove_suite(suite_id, payload):
            nonlocal changed
            for case in json.loads(payload).get("cases", []):
                trace_id = case.get("evidence_url", "").rsplit("/", 1)[-1]
                if UUID.fullmatch(trace_id):
                    (directory / "cell" / f"{trace_id}.json").unlink(missing_ok=True)
            db.execute("DELETE FROM cell_suites WHERE id=?", (suite_id,))
            changed = True

        runs = db.execute(
            "SELECT id,created_at FROM experiments ORDER BY created_at DESC"
        ).fetchall()
        for index, (run_id, created) in enumerate(runs):
            if (
                index >= max_runs
                or datetime.fromisoformat(created).timestamp() <= now - max_age
            ):
                remove_run(run_id)
        valid_runs = {r[0] for r in db.execute("SELECT id FROM experiments")}
        for path in directory.iterdir():
            if (
                UUID.fullmatch(path.name)
                and path.is_dir()
                and path.name not in valid_runs
                and not path.is_symlink()
            ):
                shutil.rmtree(path)
        suites = db.execute(
            "SELECT id,payload FROM cell_suites ORDER BY rowid DESC"
        ).fetchall()
        for index, (suite_id, payload) in enumerate(suites):
            if (
                index >= max_suites
                or datetime.fromisoformat(json.loads(payload)["created_at"]).timestamp()
                <= now - max_age
            ):
                remove_suite(suite_id, payload)
        traces = sorted(
            (
                p
                for p in (directory / "cell").glob("*.json")
                if UUID.fullmatch(p.stem) and not p.is_symlink()
            ),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for index, path in enumerate(traces):
            if index >= max_traces or path.stat().st_mtime <= now - max_age:
                path.unlink()
        files = [
            p
            for p in directory.rglob("*")
            if p.is_file() and not p.is_symlink() and p != db_path
        ]
        total = sum(p.stat().st_size for p in files)
        for path in sorted(files, key=lambda p: p.stat().st_mtime):
            if total <= max_bytes:
                break
            size = path.stat().st_size
            path.unlink(missing_ok=True)
            total -= size
        for (run_id,) in db.execute("SELECT id FROM experiments").fetchall():
            folder = directory / run_id
            if not all(
                (folder / name).is_file()
                for name in ("result.json", "manifest.json", "first_run_events.csv")
            ):
                remove_run(run_id)
        for suite_id, payload in db.execute(
            "SELECT id,payload FROM cell_suites"
        ).fetchall():
            if any(
                not (
                    directory
                    / "cell"
                    / (case["evidence_url"].rsplit("/", 1)[-1] + ".json")
                ).is_file()
                for case in json.loads(payload).get("cases", [])
                if "evidence_url" in case
            ):
                remove_suite(suite_id, payload)
        db.commit()
        if changed:
            db.execute("VACUUM")
