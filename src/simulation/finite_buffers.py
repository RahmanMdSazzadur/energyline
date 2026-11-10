"""Event-driven line with finite buffers, operators and optional synthetic timing variation."""

import argparse
import csv
import heapq
import json
import math
from collections import deque
from pathlib import Path

from single_unit import FIELDS as BASE_FIELDS, ROOT, simulate as validate_reference

from process_times import validate_timing, sample_duration
from reliability import validate_reliability, draw
from quality import validate_quality, outcome
from cell_adapter import validate_adapter, execute_cycle

FIELDS = BASE_FIELDS + ["operator_id", "defect_origin", "rework_count"]


def simulate(config):
    validate_reference(config)
    timing = validate_timing(config)
    reliability_enabled = validate_reliability(config)
    quality = validate_quality(config)
    adapter_enabled = validate_adapter(config)
    stations = config["stations"]
    n = len(stations)
    attended = [s.get("operator_attended_fraction", 1.0) for s in stations]
    if any(
        isinstance(f, bool)
        or not isinstance(f, (int, float))
        or not math.isfinite(f)
        or not 0 <= f <= 1
        for f in attended
    ):
        raise ValueError("operator_attended_fraction must be between 0 and 1")
    shared = "operator_count" in config
    operator_count = config.get("operator_count", n)
    if type(operator_count) is not int or operator_count <= 0:
        raise ValueError("operator_count must be a positive integer")
    assigned = [None] * n
    operator_busy = [0.0] * operator_count
    operator_wait = [0.0] * n
    capacities = config.get("buffer_capacities")
    if (
        not isinstance(capacities, list)
        or len(capacities) != n - 1
        or any(type(c) is not int or c < 0 for c in capacities)
    ):
        raise ValueError(
            "buffer_capacities must contain one nonnegative integer per interstation buffer"
        )
    horizon = config["shift_duration_s"] - config["planned_nonproduction_s"]
    queues = [deque() for _ in capacities]
    state = ["idle"] * n
    units = [None] * n
    times = [
        {s: 0.0 for s in ("idle", "processing", "blocked", "fault", "waiting_resume")}
        for _ in stations
    ]
    remaining = [0.0] * n
    attendance_left = [0.0] * n
    failure_count = [0] * n
    uptime_left = [draw(config, s, 0, "uptime") for s in stations]
    queue_area = [0.0] * (n - 1)
    queue_peak = [0] * (n - 1)
    entries = {}
    cell_cycles = []
    linked_cycles = {}
    accepted = []
    scrapped = []
    histories = {}
    inspected = first_pass = rework_started = rework_passed = 0
    rw_queue = deque()
    rw_unit = None
    rw_state = "idle"
    rw_times = {key: 0.0 for key in ("idle", "processing", "blocked")}
    inspection_index = n - 2 if quality else None
    rework = quality.get("rework") if quality else None
    events, snapshots, calendar = [], [], []
    now = 0.0
    released = 0
    wip_area = 0.0

    def emit(index, unit, event, result="pending"):
        history = histories.get(unit, {"origins": [], "rework_count": 0})
        is_rework = index == n
        events.append(
            dict(
                zip(
                    FIELDS,
                    [
                        config.get("run_id", "finite_buffer_reference"),
                        config["model_version"],
                        config["scenario"],
                        unit,
                        "REWORK" if is_rework else stations[index]["id"],
                        now,
                        event,
                        rw_state.upper() if is_rework else state[index].upper(),
                        result,
                        "EQUIPMENT_FAILURE" if event == "fault" else "",
                        1,
                        (
                            ("REWORK-1" if rw_state == "processing" else None)
                            if is_rework
                            else assigned[index]
                        ),
                        "|".join(history["origins"]),
                        history["rework_count"],
                    ],
                )
            )
        )

    def free_operators():
        return [i for i in range(operator_count) if i not in assigned]

    def can_start(index):
        if attended[index] == 0:
            return True
        return bool(free_operators()) if shared else assigned[index] is None

    def schedule(index):
        # One live processing event per station; completion wins exact ties.
        options = [(remaining[index], 0, "complete")]
        if assigned[index] is not None and attendance_left[index] < remaining[index]:
            options.append((attendance_left[index], 1, "operator_release"))
        if math.isfinite(uptime_left[index]):
            options.append((uptime_left[index], 2, "failure"))
        delay, _, kind = min(options)
        heapq.heappush(calendar, (now + max(0, delay), index, units[index], kind))

    def acquire(index):
        assigned[index] = (
            (free_operators()[0] if shared else index)
            if attendance_left[index] > 0
            else None
        )
        state[index] = "processing"

    def start(index, unit):
        units[index] = unit
        remaining[index] = sample_duration(config, timing, stations[index], unit)
        if stations[index].get("cell_adapter"):
            cycle = execute_cycle(config, stations[index], unit, remaining[index])
            cycle["line_started_s"] = now
            linked_cycles[unit] = cycle
            remaining[index] = cycle["line_duration_s"]
            cell_cycles.append({k: v for k, v in cycle.items() if k != "trace"})
            emit(index, unit, "cell_cycle_linked")
        attendance_left[index] = remaining[index] * attended[index]
        acquire(index)
        emit(index, unit, "started")
        schedule(index)

    def settle():
        nonlocal released, rw_unit, rw_state, rework_started
        changed = True
        while changed:
            changed = False
            # Downstream first, including direct handoff for zero-capacity buffers.
            for i in range(n - 1, -1, -1):
                if (
                    state[i] == "waiting_resume"
                    and now < horizon
                    and (attendance_left[i] == 0 or can_start(i))
                ):
                    acquire(i)
                    emit(i, units[i], "resumed")
                    schedule(i)
                    changed = True
                if (
                    i > 0
                    and state[i] == "idle"
                    and queues[i - 1]
                    and now < horizon
                    and can_start(i)
                ):
                    unit = queues[i - 1].popleft()
                    emit(i, unit, "buffer_dequeued")
                    start(i, unit)
                    changed = True
                if state[i] != "blocked":
                    continue
                unit = units[i]
                if i == n - 1:
                    accepted.append((unit, now))
                    emit(i, unit, "accepted", "pass")
                elif (
                    state[i + 1] == "idle"
                    and not queues[i]
                    and now < horizon
                    and can_start(i + 1)
                ):
                    emit(i, unit, "transferred", "pass")
                    emit(i + 1, unit, "entered")
                    start(i + 1, unit)
                elif len(queues[i]) < capacities[i]:
                    queues[i].append(unit)
                    queue_peak[i] = max(queue_peak[i], len(queues[i]))
                    emit(i, unit, "transferred", "pass")
                    emit(i + 1, unit, "buffer_enqueued")
                else:
                    continue
                units[i] = None
                state[i] = "idle"
                changed = True
            if rw_state == "blocked":
                target = n - 1
                if (
                    state[target] == "idle"
                    and not queues[target - 1]
                    and now < horizon
                    and can_start(target)
                ):
                    emit(n, rw_unit, "transferred", "pass")
                    emit(target, rw_unit, "entered")
                    start(target, rw_unit)
                elif len(queues[target - 1]) < capacities[target - 1]:
                    queues[target - 1].append(rw_unit)
                    queue_peak[target - 1] = max(
                        queue_peak[target - 1], len(queues[target - 1])
                    )
                    emit(n, rw_unit, "transferred", "pass")
                    emit(target, rw_unit, "buffer_enqueued")
                if units[target] == rw_unit or (
                    queues[target - 1] and queues[target - 1][-1] == rw_unit
                ):
                    rw_unit = None
                    rw_state = "idle"
                    changed = True
            if rw_state == "idle" and rw_queue and now < horizon:
                rw_unit = rw_queue.popleft()
                rw_state = "processing"
                histories[rw_unit]["rework_count"] = 1
                rework_started += 1
                emit(n, rw_unit, "rework_started")
                heapq.heappush(
                    calendar,
                    (now + rework["duration_s"], n, rw_unit, "rework_complete"),
                )
                changed = True
            if state[0] == "idle" and now < horizon and can_start(0):
                released += 1
                unit = f"UNIT-{released:06d}"
                entries[unit] = now
                histories[unit] = {"origins": [], "defective": False, "rework_count": 0}
                emit(0, unit, "released")
                emit(0, unit, "entered")
                start(0, unit)
                changed = True

    def snapshot():
        snapshots.append(
            {
                "timestamp_s": now,
                "queue_lengths": [len(q) for q in queues],
                "station_states": state.copy(),
                "station_units": units.copy(),
                "station_operators": assigned.copy(),
                "released_units": released,
                "accepted_units": len(accepted),
                "scrapped_units": len(scrapped),
                "rework_queue_length": len(rw_queue),
                "rework_unit": rw_unit,
                "rework_state": rw_state,
            }
        )

    def advance(target):
        nonlocal now, wip_area
        delta = target - now
        for i in range(n):
            times[i][state[i]] += delta
            if state[i] == "processing":
                remaining[i] = max(0, remaining[i] - delta)
                uptime_left[i] = max(0, uptime_left[i] - delta)
                if assigned[i] is not None:
                    attendance_left[i] = max(0, attendance_left[i] - delta)
            if assigned[i] is not None:
                operator_busy[assigned[i]] += delta
            has_work = i == 0 or bool(queues[i - 1]) or state[i - 1] == "blocked"
            if state[i] == "idle" and has_work and not can_start(i):
                operator_wait[i] += delta
        for i, queue in enumerate(queues):
            queue_area[i] += len(queue) * delta
        rw_times[rw_state] += delta
        wip_area += (released - len(accepted) - len(scrapped)) * delta
        now = target

    settle()
    snapshot()
    while calendar and calendar[0][0] <= horizon:
        advance(calendar[0][0])
        # Complete all simultaneous operations before trying transfers.
        while calendar and calendar[0][0] == now:
            _, i, unit, kind = heapq.heappop(calendar)
            if kind == "rework_complete":
                if rw_state != "processing" or rw_unit != unit:
                    raise RuntimeError("Invalid rework completion")
                if outcome(
                    config, unit, "rework", "REWORK", rework["success_probability"]
                ):
                    histories[unit]["defective"] = False
                    rework_passed += 1
                    emit(n, unit, "rework_passed", "pass")
                    rw_state = "blocked"
                else:
                    emit(n, unit, "scrapped", "fail")
                    scrapped.append((unit, now))
                    rw_unit = None
                    rw_state = "idle"
                continue
            if units[i] != unit:
                raise RuntimeError("Event unit does not match station")
            if kind == "repair":
                if state[i] != "fault":
                    raise RuntimeError("Repair without fault")
                state[i] = "waiting_resume"
                emit(i, unit, "repaired")
                uptime_left[i] = draw(config, stations[i], failure_count[i], "uptime")
                continue
            if state[i] != "processing":
                raise RuntimeError("Processing event on inactive station")
            if kind == "operator_release":
                emit(i, unit, "operator_released")
                assigned[i] = None
                attendance_left[i] = 0
                schedule(i)
            elif kind == "failure":
                state[i] = "fault"
                emit(i, unit, "fault")
                assigned[i] = None
                failure_count[i] += 1
                repair = draw(config, stations[i], failure_count[i], "repair")
                heapq.heappush(calendar, (now + repair, i, unit, "repair"))
            else:
                state[i] = "blocked"
                emit(
                    i,
                    unit,
                    "completed",
                    "pending" if quality and i <= inspection_index else "pass",
                )
                assigned[i] = None
                attendance_left[i] = 0
                if stations[i].get("cell_adapter"):
                    cycle = linked_cycles[unit]
                    if cycle["outcome"] == "quarantined":
                        histories[unit]["origins"].append("S3")
                        emit(i, unit, "cell_quarantined", "fail")
                        emit(i, unit, "scrapped", "fail")
                        scrapped.append((unit, now))
                        units[i] = None
                        state[i] = "idle"
                        continue
                    if cycle["outcome"] == "fail":
                        histories[unit]["origins"].append("S3")
                        histories[unit]["defective"] = True
                        emit(i, unit, "cell_failed_result", "fail")
                if quality:
                    p = quality.get("defect_probabilities", {}).get(
                        stations[i]["id"], 0
                    )
                    if outcome(config, unit, "defect", stations[i]["id"], p):
                        histories[unit]["origins"].append(stations[i]["id"])
                        histories[unit]["defective"] = True
                        emit(i, unit, "defect_created", "pending")
                    if i == inspection_index:
                        inspected += 1
                        if histories[unit]["defective"]:
                            emit(i, unit, "rejected", "fail")
                            if rework is not None:
                                rw_queue.append(unit)
                                emit(n, unit, "rework_queued")
                            else:
                                emit(i, unit, "scrapped", "fail")
                                scrapped.append((unit, now))
                            units[i] = None
                            state[i] = "idle"
                        else:
                            first_pass += 1
                            emit(i, unit, "inspection_passed", "pass")
        settle()
        for i in range(n - 1):
            if state[i] == "blocked":
                emit(i, units[i], "blocked", "pass")
        snapshot()
    if now < horizon:
        if not calendar and released > len(accepted) + len(scrapped):
            raise RuntimeError(
                "Deadlock: unfinished units with no future processing events"
            )
        advance(horizon)
        snapshot()
    unfinished = (
        sum(unit is not None for unit in units)
        + sum(map(len, queues))
        + len(rw_queue)
        + int(rw_unit is not None)
    )
    if released != len(accepted) + len(scrapped) + unfinished:
        raise RuntimeError("Unit conservation failed")
    accepted_ids = {u for u, _ in accepted}
    scrapped_ids = {u for u, _ in scrapped}
    summary = {
        "model": (
            ("stochastic_shared_operators" if shared else "stochastic_finite_buffers")
            if timing["distribution"] != "fixed"
            else (
                "deterministic_shared_operators"
                if shared
                else "deterministic_finite_buffers"
            )
        ),
        "input_source": config["input_source"],
        "run_id": config.get("run_id", "finite_buffer_reference"),
        "model_version": config["model_version"],
        "scenario": config["scenario"],
        "processing_time": timing,
        "seed": config.get("seed"),
        "reliability_enabled": reliability_enabled,
        "failure_clock": "processing_time_only",
        "interruption_policy": "resume remaining work; release operator on fault; reacquire if attendance remains",
        "reliability": {s["id"]: s.get("reliability") for s in stations},
        "production_window_s": horizon,
        "target_good_units": config["target_good_units"],
        "released_units": released,
        "accepted_units": len(accepted),
        "scrapped_units": len(scrapped),
        "unfinished_units": unfinished,
        "demand_met": len(accepted) >= config["target_good_units"],
        "first_completion_s": accepted[0][1] if accepted else None,
        "mean_accepted_lead_time_s": (
            sum(t - entries[u] for u, t in accepted) / len(accepted)
            if accepted
            else None
        ),
        "time_weighted_mean_wip": wip_area / horizon,
        "staffing_mode": "shared_pool" if shared else "dedicated",
        "operator_count": operator_count,
        "paid_labor_hours": (operator_count + int(rework is not None))
        * config["shift_duration_s"]
        / 3600,
        "good_units_per_paid_labor_hour": len(accepted)
        / (
            (operator_count + int(rework is not None))
            * config["shift_duration_s"]
            / 3600
        ),
        "operators": [
            {
                "operator_id": i,
                "productive_time_s": busy,
                "utilization_of_production_window": busy / horizon,
            }
            for i, busy in enumerate(operator_busy)
        ],
        "stations": [
            {
                "station_id": station["id"],
                "productive_time_s": times[i]["processing"],
                "blocked_time_s": times[i]["blocked"],
                "starved_time_s": times[i]["idle"] - operator_wait[i],
                "waiting_for_operator_time_s": operator_wait[i]
                + times[i]["waiting_resume"],
                "fault_time_s": times[i]["fault"],
                "failure_count": failure_count[i],
                "utilization": times[i]["processing"] / horizon,
                "blocking_fraction": times[i]["blocked"] / horizon,
            }
            for i, station in enumerate(stations)
        ],
        "cell_integration": {
            "enabled": adapter_enabled,
            "cycles": cell_cycles,
            "interpretation": "Independent per-unit cell execution; explicitly scaled cycle duration; not a real-time PLC connection",
        },
        "quality": quality,
        "first_inspections": inspected,
        "first_pass_units": first_pass,
        "first_pass_yield": first_pass / inspected if inspected else None,
        "rework_started_units": rework_started,
        "rework_passed_units": rework_passed,
        "accepted_after_rework": sum(
            histories[u]["rework_count"] > 0 for u, _ in accepted
        ),
        "rework_resource": {
            "dedicated_operators": int(rework is not None),
            "processing_time_s": rw_times["processing"],
            "blocked_time_s": rw_times["blocked"],
            "queued_at_shift_end": len(rw_queue),
            "unit_at_shift_end": rw_unit,
        },
        "unit_records": (
            [
                {
                    "unit_id": u,
                    "defect_origins": h["origins"],
                    "rework_count": h["rework_count"],
                    "disposition": (
                        "accepted"
                        if u in accepted_ids
                        else "scrapped" if u in scrapped_ids else "unfinished"
                    ),
                }
                for u, h in histories.items()
            ]
            if quality
            else []
        ),
        "buffers": [
            {
                "from_station": stations[i]["id"],
                "to_station": stations[i + 1]["id"],
                "capacity": cap,
                "peak_waiting_units": queue_peak[i],
                "final_waiting_units": len(queues[i]),
                "time_weighted_mean_waiting_units": queue_area[i] / horizon,
            }
            for i, cap in enumerate(capacities)
        ],
        "assumptions": [
            (
                "Synthetic symmetric triangular times around assumed means"
                if timing["distribution"] == "triangular"
                else "Synthetic fixed times"
            ),
            "Empty start; no overtime",
            "FIFO finite buffers exclude units held at stations",
            "Blocking after service; zero transfer time",
            "Zero capacity means direct handoff; completed unit stays upstream until downstream ready",
            (
                "Shared operator pool; downstream-first nonpreemptive allocation"
                if shared
                else "Dedicated operator per station"
            ),
            "Operator attends initial configured fraction of each cycle; remainder is unattended",
            "No separate unload or transfer labor; operator released before blocking",
            "All operators skilled at all tasks; no walking or transfer labor",
            "Unlimited input supply; release only when S1 is free",
            (
                "Synthetic processing-time failure clocks; independent repairs; no repair labor resource"
                if reliability_enabled
                else "No failures"
            ),
            (
                "Perfect inspection at penultimate station; one offline rework attempt; successful units rejoin final labeling"
                if quality
                else "No scrap or rework; all inspections pass"
            ),
            "When enabled, rework uses one separate paid operator and an unlimited FIFO input queue",
            "Breaks removed into one contiguous production window",
            "Completions at shift end count; no new operation starts at shift end",
        ],
    }
    return events, summary, snapshots


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/finite_buffers")
    parser.add_argument(
        "--config", type=Path, default=ROOT / "configs/finite_baseline.json"
    )
    args = parser.parse_args()
    events, summary, snapshots = simulate(json.loads(args.config.read_text()))
    destination = args.output
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / "events.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(events)
    for name, value in [("summary", summary), ("snapshots", snapshots)]:
        (destination / f"{name}.json").write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
