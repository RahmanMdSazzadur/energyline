"""EnergyLine experiment API and browser dashboard. Standard library only."""

import argparse
from contextlib import closing
import copy
import csv
import hashlib
import json
import os
import platform
import re
import sqlite3
import statistics
import sys
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(ROOT / "src/simulation"),
    str(ROOT / "src/analysis"),
    str(ROOT / "src/cell"),
]
from finite_buffers import FIELDS, simulate
from parallel_manual import simulate as simulate_parallel
from variability_experiments import percentile, wilson_interval
from s3_demo import run_demo, DEMOS

SCENARIOS = {
    "manual": ("Manual baseline", "configs/variable_times.json"),
    "faster_s3": ("Faster S3", "configs/scenarios/C_faster_s3.json"),
    "faster_s2_s3": ("Faster S2 and S3", "configs/scenarios/D_faster_s2_s3.json"),
    "parallel_s3": ("Two manual S3 fixtures", "configs/parallel_manual.json"),
    "integrated_s3": ("S3 controller linked to line", "configs/integrated_s3.json"),
    "quality_rework": (
        "Faster S2/S3 + failures and rework",
        "configs/quality_baseline.json",
    ),
}


class ConflictError(ValueError):
    pass


class ExperimentService:
    def __init__(self, directory=None):
        self.directory = Path(directory or os.environ.get("ENERGYLINE_DATA_DIR") or ROOT / "results/experiments")
        self.directory.mkdir(parents=True, exist_ok=True)
        self.database = self.directory / "experiments.sqlite3"
        self.lock = threading.Lock()
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS experiments (id TEXT PRIMARY KEY, request_id TEXT UNIQUE, fingerprint TEXT, created_at TEXT, scenario TEXT, payload TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS cell_suites (id TEXT PRIMARY KEY, request_id TEXT UNIQUE, fingerprint TEXT, payload TEXT)"
            )

    def scenarios(self):
        return [{"id": key, "label": value[0]} for key, value in SCENARIOS.items()]

    def prepare(self, request):
        if not isinstance(request, dict):
            raise ValueError("Request must be a JSON object")
        allowed = {
            "scenario",
            "operators",
            "replications",
            "seed",
            "target",
            "request_id",
        }
        if set(request) - allowed:
            raise ValueError("Unknown request fields")
        scenario = request.get("scenario", "quality_rework")
        if not isinstance(scenario, str) or scenario not in SCENARIOS:
            raise ValueError("Choose a known scenario")
        values = {}
        for key, default, minimum, maximum in [
            ("operators", 3, 1, 5),
            ("replications", 30, 1, 100),
            ("seed", 20261109, 0, 2147483547),
            ("target", 240, 1, 1000),
        ]:
            value = request.get(key, default)
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError(
                    f"{key} must be an integer between {minimum} and {maximum}"
                )
            values[key] = value
        request_id = request.get("request_id")
        if request_id is not None and (
            not isinstance(request_id, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", request_id)
        ):
            raise ValueError(
                "request_id must be 8–80 letters, digits, hyphens or underscores"
            )
        config = json.loads((ROOT / SCENARIOS[scenario][1]).read_text())
        config.update(
            operator_count=values["operators"],
            target_good_units=values["target"],
            model_version="1.0.0-software",
        )
        params = dict(scenario=scenario, **values)
        source_hashes = {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ("simulation", "controls", "equipment_model", "cell")
            for p in sorted((ROOT / "src" / folder).glob("*.py"))
        }
        fingerprint = hashlib.sha256(
            json.dumps(
                {"parameters": params, "config": config, "sources": source_hashes},
                sort_keys=True,
            ).encode()
        ).hexdigest()
        return params, config, request_id, fingerprint, source_hashes

    def run(self, request):
        params, config, request_id, fingerprint, source_hashes = self.prepare(request)
        with self.lock:
            with closing(sqlite3.connect(self.database)) as db, db:
                if request_id:
                    existing = db.execute(
                        "SELECT fingerprint,payload FROM experiments WHERE request_id=?",
                        (request_id,),
                    ).fetchone()
                    if existing:
                        if existing[0] != fingerprint:
                            raise ConflictError(
                                "This request_id was already used for different inputs or model code"
                            )
                        return json.loads(existing[1])
            experiment_id = str(uuid.uuid4())
            created_at = datetime.now(timezone.utc).isoformat()
            results = []
            first_events = first_summary = None
            for replication in range(params["replications"]):
                run_config = copy.deepcopy(config)
                run_config.update(
                    seed=params["seed"] + replication,
                    run_id=f"{experiment_id}_rep_{replication+1:03d}",
                )
                engine = (
                    simulate_parallel
                    if run_config.get("parallel_servers")
                    else simulate
                )
                events, summary, _ = engine(run_config)
                if first_events is None:
                    first_events, first_summary = events, summary
                results.append(
                    {
                        key: summary[key]
                        for key in [
                            "run_id",
                            "seed",
                            "accepted_units",
                            "scrapped_units",
                            "unfinished_units",
                            "released_units",
                            "first_pass_yield",
                            "accepted_after_rework",
                            "good_units_per_paid_labor_hour",
                            "demand_met",
                        ]
                    }
                )
            output = [r["accepted_units"] for r in results]
            successes = sum(r["demand_met"] for r in results)
            low, high = wilson_interval(successes, len(results))
            result = {
                "id": experiment_id,
                "created_at": created_at,
                "parameters": params,
                "input_source": "synthetic_assumption",
                "model_version": "1.0.0-software",
                "aggregate": {
                    "mean_good_units": statistics.mean(output),
                    "minimum": min(output),
                    "maximum": max(output),
                    "p05": percentile(output, 0.05),
                    "p95": percentile(output, 0.95),
                    "successful_shifts": successes,
                    "replications": len(results),
                    "observed_demand_attainment": successes / len(results),
                    "wilson_95_lower": low,
                    "wilson_95_upper": high,
                    "mean_scrapped_units": statistics.mean(
                        r["scrapped_units"] for r in results
                    ),
                    "mean_unfinished_units": statistics.mean(
                        r["unfinished_units"] for r in results
                    ),
                    "mean_labor_productivity": statistics.mean(
                        r["good_units_per_paid_labor_hour"] for r in results
                    ),
                },
                "runs": results,
                "representative_run": {
                    k: v for k, v in first_summary.items() if k != "unit_records"
                },
                "diagnostics_scope": "Station diagnostics describe the first replication only",
                "limitations": [
                    "Synthetic inputs; no industrial or measured performance claim",
                    "Walking, unloading and repair labor constraints are omitted",
                    "Rework scenario adds one dedicated paid operator",
                    "Confidence interval covers sampling uncertainty within this model only",
                ],
                "artifacts": {
                    "first_run_events": f"/api/experiments/{experiment_id}/events.csv",
                    "result": f"/api/experiments/{experiment_id}",
                },
            }
            folder = self.directory / experiment_id
            folder.mkdir()
            with (folder / "first_run_events.csv").open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(first_events[0]))
                writer.writeheader()
                writer.writerows(first_events)
            manifest = {
                "parameters": params,
                "base_config": config,
                "source_sha256": source_hashes,
                "python_version": platform.python_version(),
                "seeds": [r["seed"] for r in results],
                "trace_scope": "Only first replication event trace retained; all run summaries retained",
                "request_id": request_id,
            }
            (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
            payload = json.dumps(result)
            (folder / "result.json").write_text(json.dumps(result, indent=2) + "\n")
            with closing(sqlite3.connect(self.database)) as db, db:
                db.execute(
                    "INSERT INTO experiments VALUES (?,?,?,?,?,?)",
                    (
                        experiment_id,
                        request_id,
                        fingerprint,
                        created_at,
                        params["scenario"],
                        payload,
                    ),
                )
            return result

    def commission(self, request):
        if not isinstance(request, dict) or set(request) - {"request_id"}:
            raise ValueError("Commissioning accepts only an optional request_id")
        request_id = request.get("request_id")
        if request_id is not None and (
            not isinstance(request_id, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", request_id)
        ):
            raise ValueError("Invalid commissioning request_id")
        hashes = {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ("controls", "equipment_model", "cell")
            for p in sorted((ROOT / "src" / folder).glob("*.py"))
        }
        fingerprint = hashlib.sha256(
            json.dumps(hashes, sort_keys=True).encode()
        ).hexdigest()
        with self.lock:
            with closing(sqlite3.connect(self.database)) as db, db:
                existing = (
                    db.execute(
                        "SELECT fingerprint,payload FROM cell_suites WHERE request_id=?",
                        (request_id,),
                    ).fetchone()
                    if request_id
                    else None
                )
            if existing:
                if existing[0] != fingerprint:
                    raise ConflictError(
                        "This commissioning request_id belongs to a different model version"
                    )
                return json.loads(existing[1])
            suite_id = str(uuid.uuid4())
            cases = []
            folder = self.directory / "cell"
            folder.mkdir(exist_ok=True)
            for name in DEMOS:
                try:
                    trace = run_demo(name)
                    trace_id = str(uuid.uuid4())
                    trace.update(
                        id=trace_id,
                        created_at=datetime.now(timezone.utc).isoformat(),
                        suite_id=suite_id,
                    )
                    trace["artifact"] = f"/api/cell/runs/{trace_id}"
                    (folder / f"{trace_id}.json").write_text(
                        json.dumps(trace, indent=2) + "\n"
                    )
                    cases.append(
                        {
                            "demo": name,
                            "label": trace["label"],
                            "passed": trace["passed"],
                            "expected_fault": trace["expected_fault"],
                            "checks": trace["checks"],
                            "completion_records": sum(
                                e["event_type"] == "completed" for e in trace["events"]
                            ),
                            "evidence_url": trace["artifact"],
                        }
                    )
                except Exception as error:
                    cases.append(
                        {
                            "demo": name,
                            "label": DEMOS[name][0],
                            "passed": False,
                            "error": f"{type(error).__name__}: {error}",
                        }
                    )
            passed_count = sum(case["passed"] for case in cases)
            report = {
                "id": suite_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "model_version": "0.2.0",
                "input_source": "synthetic_equipment_model",
                "total_cases": len(cases),
                "passed_cases": passed_count,
                "failed_cases": len(cases) - passed_count,
                "passed": passed_count == len(cases),
                "cases": cases,
                "source_sha256": hashes,
                "report_url": f"/api/cell/suites/{suite_id}",
                "limitations": [
                    "Scripted software commissioning only; no physical hardware validation",
                    "Accelerated timings are separate from production-flow timing assumptions",
                    "Inapplicable conditional checks pass by definition; independent unit tests are separate",
                ],
            }
            with closing(sqlite3.connect(self.database)) as db, db:
                db.execute(
                    "INSERT INTO cell_suites VALUES (?,?,?,?)",
                    (suite_id, request_id, fingerprint, json.dumps(report)),
                )
            return report

    def get_commissioning(self, suite_id):
        with closing(sqlite3.connect(self.database)) as db, db:
            row = db.execute(
                "SELECT payload FROM cell_suites WHERE id=?", (suite_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def list(self):
        with closing(sqlite3.connect(self.database)) as db, db:
            records = db.execute(
                "SELECT id,created_at,scenario,payload FROM experiments ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
        return [
            {
                "id": i,
                "created_at": date,
                "scenario": scenario,
                "parameters": json.loads(payload)["parameters"],
                "aggregate": json.loads(payload)["aggregate"],
            }
            for i, date, scenario, payload in records
        ]

    def get(self, experiment_id):
        with closing(sqlite3.connect(self.database)) as db, db:
            row = db.execute(
                "SELECT payload FROM experiments WHERE id=?", (experiment_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None


def byte_range(header, size):
    if not header:
        return 0, size - 1, False
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", header)
    if not match or not any(match.groups()) or size <= 0:
        raise ValueError("Invalid byte range")
    a, b = match.groups()
    if a:
        start = int(a)
        end = min(int(b), size - 1) if b else size - 1
    else:
        length = int(b)
        if length <= 0:
            raise ValueError("Invalid suffix range")
        start = max(0, size - length)
        end = size - 1
    if start >= size or end < start:
        raise ValueError("Unsatisfiable byte range")
    return start, end, True


def handler_for(service):
    public_demo = os.environ.get("ENERGYLINE_PUBLIC_DEMO") == "1"
    release_url = os.environ.get("ENERGYLINE_RELEASE_URL", "")
    job_slot = threading.BoundedSemaphore(1)

    class Handler(BaseHTTPRequestHandler):
        def send_data(self, status, value, mime="application/json"):
            data = json.dumps(value).encode() if mime == "application/json" else value
            if public_demo and mime.startswith("text/html"):
                notice = b'<aside role="note" style="padding:12px 24px;background:#fff3d1;color:#453817;font:14px/1.5 system-ui">Public demo: experiments are shared and temporary. Saved runs may disappear when the free service sleeps or restarts. Download results you want to keep.</aside>'
                data = data.replace(b"<body>", b"<body>" + notice, 1)
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def send_file(self, path, mime):
            if not path.exists():
                return self.send_data(404, {"error": "Artifact not generated yet"})
            size = path.stat().st_size
            try:
                start, end, partial = byte_range(self.headers.get("Range"), size)
            except ValueError:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            self.send_response(206 if partial else 200)
            self.send_header("Content-Type", mime)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(max(0, end - start + 1)))
            if partial:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            with path.open("rb") as handle:
                handle.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    data = handle.read(min(65536, remaining))
                    if not data:
                        break
                    self.wfile.write(data)
                    remaining -= len(data)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/downloads/release.zip" and public_demo and release_url:
                self.send_response(302)
                self.send_header("Location", release_url)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            artifacts = {
                "/media/demo.mp4": ("media/EnergyLine_demo.mp4", "video/mp4"),
                "/media/demo.srt": ("media/demo.srt", "text/plain; charset=utf-8"),
                "/design/module.svg": (
                    "cad/product/module_dimensioned.svg",
                    "image/svg+xml",
                ),
                "/design/fixture.svg": (
                    "cad/fixture/fixture_dimensioned.svg",
                    "image/svg+xml",
                ),
                "/design/layout.svg": ("cad/layout/line_layout.svg", "image/svg+xml"),
                "/downloads/case-study.md": (
                    "docs/final_case_study.md",
                    "text/markdown; charset=utf-8",
                ),
                "/downloads/release.zip": (
                    "release/EnergyLine-v1.1.1-final.zip",
                    "application/zip",
                ),
                "/api/portfolio": (
                    "results/final/release_status.json",
                    "application/json",
                ),
                "/api/final-evidence": (
                    "results/final/integrated_comparison.json",
                    "application/json",
                ),
            }
            if path in artifacts:
                file, mime = artifacts[path]
                return self.send_file(ROOT / file, mime)
            if path == "/api/health":
                return self.send_data(200, {"status": "ok", "service": "EnergyLine", "public_demo": public_demo})
            if path == "/api/costs":
                report = ROOT / "results/economics/comparison.json"
                if not report.exists():
                    return self.send_data(
                        404, {"error": "Cost comparison has not been generated"}
                    )
                return self.send_data(200, json.loads(report.read_text()))
            if path == "/api/cell/demos":
                return self.send_data(
                    200,
                    [
                        {"id": key, "label": value[0], "expected_fault": value[1]}
                        for key, value in DEMOS.items()
                    ],
                )
            suite_match = re.fullmatch(r"/api/cell/suites/([0-9a-f-]{36})", path)
            if suite_match:
                report = service.get_commissioning(suite_match[1])
                return (
                    self.send_data(200, report)
                    if report
                    else self.send_data(
                        404, {"error": "Commissioning report not found"}
                    )
                )
            cell_match = re.fullmatch(r"/api/cell/runs/([0-9a-f-]{36})", path)
            if cell_match:
                artifact = service.directory / "cell" / f"{cell_match[1]}.json"
                if not artifact.exists():
                    return self.send_data(404, {"error": "Cell run not found"})
                return self.send_data(200, json.loads(artifact.read_text()))
            if path == "/api/scenarios":
                return self.send_data(200, service.scenarios())
            if path == "/api/experiments":
                return self.send_data(200, service.list())
            match = re.fullmatch(
                r"/api/experiments/([0-9a-f-]{36})(/events.csv)?", path
            )
            if match:
                result = service.get(match[1])
                if result is None:
                    return self.send_data(404, {"error": "Experiment not found"})
                if match[2]:
                    data = (
                        service.directory / match[1] / "first_run_events.csv"
                    ).read_bytes()
                    return self.send_data(200, data, "text/csv; charset=utf-8")
                return self.send_data(200, result)
            static = {
                "/circuit-simulation": ("circuit_simulation.html", "text/html; charset=utf-8"),
                "/review": ("engineering_review.html", "text/html; charset=utf-8"),
                "/portfolio": ("portfolio.html", "text/html; charset=utf-8"),
                "/case-study": ("case_study.html", "text/html; charset=utf-8"),
                "/costs": ("costs.html", "text/html; charset=utf-8"),
                "/costs.js": ("costs.js", "text/javascript; charset=utf-8"),
                "/costs.css": ("costs.css", "text/css; charset=utf-8"),
                "/cell": ("cell.html", "text/html; charset=utf-8"),
                "/cell.js": ("cell.js", "text/javascript; charset=utf-8"),
                "/cell.css": ("cell.css", "text/css; charset=utf-8"),
                "/": ("index.html", "text/html; charset=utf-8"),
                "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                "/style.css": ("style.css", "text/css; charset=utf-8"),
            }
            if path in static:
                name, mime = static[path]
                return self.send_data(200, (ROOT / "web" / name).read_bytes(), mime)
            self.send_data(404, {"error": "Not found"})

        def do_POST(self):
            path = urlparse(self.path).path
            if path not in (
                "/api/experiments",
                "/api/cell/demo",
                "/api/cell/commission",
            ):
                return self.send_data(404, {"error": "Not found"})
            # Browser requests must be same-origin. Server-to-server n8n requests have no Origin.
            origin = self.headers.get("Origin")
            if origin and urlparse(origin).netloc != self.headers.get("Host"):
                return self.send_data(
                    403, {"error": "Cross-origin requests are not allowed"}
                )
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.send_data(415, {"error": "Send application/json"})
            if public_demo and not job_slot.acquire(blocking=False):
                return self.send_data(429, {"error": "The public demo is running another job. Please try again shortly."})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096:
                    raise ValueError("Request body must be 1–4096 bytes")
                request = json.loads(self.rfile.read(length))
                if path == "/api/cell/commission":
                    result = service.commission(request)
                elif path == "/api/cell/demo":
                    if not isinstance(request, dict) or set(request) != {"demo"}:
                        raise ValueError("Cell request must contain only a demo name")
                    result = run_demo(request["demo"])
                    result.update(
                        id=str(uuid.uuid4()),
                        created_at=datetime.now(timezone.utc).isoformat(),
                    )
                    result["artifact"] = f"/api/cell/runs/{result['id']}"
                    folder = service.directory / "cell"
                    folder.mkdir(exist_ok=True)
                    (folder / f"{result['id']}.json").write_text(
                        json.dumps(result, indent=2) + "\n"
                    )
                else:
                    result = service.run(request)
                self.send_data(200, result)
            except ConflictError as error:
                self.send_data(409, {"error": str(error)})
            except (ValueError, TypeError) as error:
                self.send_data(400, {"error": str(error)})
            except Exception:
                self.log_error("Experiment failed")
                self.send_data(500, {"error": "Experiment failed; inspect server logs"})
            finally:
                if public_demo:
                    job_slot.release()

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8787")))
    args = parser.parse_args()
    server = ThreadingHTTPServer(
        (args.host, args.port), handler_for(ExperimentService())
    )
    print(f"EnergyLine dashboard listening on {args.host}:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
