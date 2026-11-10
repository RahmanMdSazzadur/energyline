"""Deterministic line: infinite buffers, FIFO, dedicated station resources."""

import argparse
import csv
import json
from pathlib import Path

from single_unit import FIELDS, ROOT, simulate as validate_reference


def simulate(config):
    # Share the reference model's station and production-window validation.
    validate_reference(config)
    horizon = config["shift_duration_s"] - config["planned_nonproduction_s"]
    stations = config["stations"]
    available = [0.0] * len(stations)
    busy = [0.0] * len(stations)
    waits = [[] for _ in stations]
    events = []
    accepted = 0
    released = 0
    lead_times = []
    wip_area = 0.0

    def emit(unit, index, time, event, state, result="pending"):
        events.append(
            dict(
                zip(
                    FIELDS,
                    [
                        "multi_unit_reference",
                        config["model_version"],
                        config["scenario"],
                        unit,
                        stations[index]["id"],
                        time,
                        event,
                        state,
                        result,
                        "",
                        1,
                    ],
                )
            )
        )

    # Units enter only when S1 is ready: no artificial infinite input queue.
    while available[0] < horizon:
        released += 1
        unit = f"UNIT-{released:06d}"
        entry = available[0]
        arrival = entry
        complete = False
        emit(unit, 0, entry, "released", "IN_LINE")
        for index, station in enumerate(stations):
            emit(unit, index, arrival, "entered", "QUEUED")
            start = max(arrival, available[index])
            waits[index].append((arrival, min(start, horizon)))
            if start >= horizon:
                break
            emit(unit, index, start, "started", "PROCESSING")
            finish = start + station["mean_process_s"]
            available[index] = finish
            busy[index] += min(finish, horizon) - start
            if finish > horizon:
                emit(unit, index, horizon, "shift_ended", "PROCESSING")
                break
            emit(unit, index, finish, "completed", "DONE", "pass")
            arrival = finish
            if index == len(stations) - 1:
                accepted += 1
                complete = True
                lead_times.append(finish - entry)
                emit(unit, index, finish, "accepted", "RELEASED", "pass")
        wip_area += (arrival if complete else horizon) - entry

    # Stable sorting preserves each unit's causal ordering for simultaneous events.
    events.sort(key=lambda event: event["timestamp_s"])
    metrics = []
    for index, station in enumerate(stations):
        changes = {}
        for arrival, start in waits[index]:
            if start > arrival:
                changes[arrival] = changes.get(arrival, 0) + 1
                changes[start] = changes.get(start, 0) - 1
        queue = peak = 0
        for time in sorted(changes):
            queue += changes[time]
            peak = max(peak, queue)
        metrics.append(
            {
                "station_id": station["id"],
                "productive_time_s": busy[index],
                "utilization": busy[index] / horizon,
                "peak_waiting_units": peak,
                "time_weighted_mean_waiting_units": sum(b - a for a, b in waits[index])
                / horizon,
            }
        )
    return events, {
        "model": "deterministic_multi_unit_infinite_buffers",
        "input_source": config["input_source"],
        "production_window_s": horizon,
        "target_good_units": config["target_good_units"],
        "released_units": released,
        "accepted_units": accepted,
        "scrapped_units": 0,
        "unfinished_units": released - accepted,
        "demand_met": accepted >= config["target_good_units"],
        "first_completion_s": next(
            (e["timestamp_s"] for e in events if e["event_type"] == "accepted"), None
        ),
        "mean_accepted_lead_time_s": (
            sum(lead_times) / len(lead_times) if lead_times else None
        ),
        "time_weighted_mean_wip": wip_area / horizon,
        "stations": metrics,
        "assumptions": [
            "Synthetic fixed station times",
            "Empty start; no overtime",
            "Unlimited FIFO buffers; zero transfer time",
            "One dedicated resource per station; no shared operators",
            "Unlimited material supply; release when S1 available",
            "No failures, scrap or rework; all inspections pass",
            "Breaks removed into one contiguous production window",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/baseline.json")
    args = parser.parse_args()
    events, summary = simulate(json.loads(args.config.read_text()))
    destination = ROOT / "results/multi_unit"
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / "events.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(events)
    (destination / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
