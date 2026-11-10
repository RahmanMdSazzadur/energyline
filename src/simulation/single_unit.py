"""Deterministic single-unit reference model using only standard Python."""

import argparse
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIELDS = [
    "run_id",
    "model_version",
    "scenario",
    "unit_id",
    "station_id",
    "timestamp_s",
    "event_type",
    "state",
    "result",
    "fault_code",
    "cycle_number",
]


def simulate(config):
    stations = config["stations"]
    if not stations or len({s["id"] for s in stations}) != len(stations):
        raise ValueError("Stations must be nonempty with unique IDs")
    for station in stations:
        duration = station["mean_process_s"]
        if (
            isinstance(duration, bool)
            or not isinstance(duration, (int, float))
            or not math.isfinite(duration)
            or duration <= 0
        ):
            raise ValueError("Each processing time must be finite and positive")
    available = config["shift_duration_s"] - config["planned_nonproduction_s"]
    if available <= 0:
        raise ValueError("Production window must be positive")
    events = []
    now = 0

    def emit(station, event, state, result="pending"):
        events.append(
            dict(
                zip(
                    FIELDS,
                    [
                        "single_unit_reference",
                        config["model_version"],
                        config["scenario"],
                        "UNIT-000001",
                        station,
                        now,
                        event,
                        state,
                        result,
                        "",
                        1,
                    ],
                )
            )
        )

    finished = True
    for station in stations:
        if now >= available:
            finished = False
            break
        emit(station["id"], "entered", "READY")
        emit(station["id"], "started", "PROCESSING")
        finish = now + station["mean_process_s"]
        if finish > available:
            now = available
            emit(station["id"], "shift_ended", "PROCESSING")
            finished = False
            break
        now = finish
        emit(station["id"], "completed", "DONE", "pass")
    if finished:
        emit(stations[-1]["id"], "accepted", "RELEASED", "pass")
    summary = {
        "model": "deterministic_single_unit_reference",
        "input_source": config["input_source"],
        "released_units": 1,
        "accepted_units": int(finished),
        "scrapped_units": 0,
        "unfinished_units": int(not finished),
        "completion_time_s": now if finished else None,
        "production_window_s": available,
        "assumptions": [
            "One unit only",
            "Fixed processing times",
            "Zero transfer time",
            "Dedicated resource available at each station",
            "No failures; all completed inspections pass",
            "Planned nonproduction time removed into one contiguous window",
            "No overtime; no production throughput prediction",
        ],
    }
    return events, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/baseline.json")
    args = parser.parse_args()
    events, summary = simulate(json.loads(args.config.read_text()))
    destination = ROOT / "results/single_unit"
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / "events.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(events)
    (destination / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
