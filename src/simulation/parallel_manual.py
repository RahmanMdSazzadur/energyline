"""Manual FIFO line with multiple physical stations per operation and finite buffers.

All processing is attended; failures/unattended cycles are intentionally unsupported.
"""

import heapq
from collections import deque
from single_unit import FIELDS as BASE_FIELDS, simulate as validate_reference
from process_times import validate_timing, sample_duration
from quality import validate_quality, outcome

FIELDS = BASE_FIELDS + ["operator_id", "defect_origin", "rework_count", "resource_id"]


def simulate(config):
    validate_reference(config)
    timing = validate_timing(config)
    quality = validate_quality(config)
    stages = config["stations"]
    n = len(stages)
    count = config.get("operator_count", n)
    if type(count) is not int or count <= 0:
        raise ValueError("operator_count must be positive")
    if any(
        s.get("reliability")
        or s.get("operator_attended_fraction", 1) != 1
        or s.get("cell_adapter")
        for s in stages
    ):
        raise ValueError(
            "Parallel manual engine supports fully attended, failure-free operations only"
        )
    servers = config.get("parallel_servers", [1] * n)
    capacities = config.get("buffer_capacities")
    if (
        len(servers) != n
        or any(type(v) is not int or v < 1 for v in servers)
        or servers[0] != 1
    ):
        raise ValueError("Positive server count per stage required; S1 has one server")
    if (
        not isinstance(capacities, list)
        or len(capacities) != n - 1
        or any(type(v) is not int or v < 0 for v in capacities)
    ):
        raise ValueError("Invalid buffer capacities")
    horizon = config["shift_duration_s"] - config["planned_nonproduction_s"]
    workers = []
    groups = []
    for stage, number in enumerate(servers):
        group = []
        for slot in range(number):
            group.append(len(workers))
            workers.append(
                {
                    "stage": stage,
                    "resource_id": f"{stages[stage]['id']}-{slot+1}",
                    "state": "idle",
                    "unit": None,
                    "operator": None,
                    "processing": 0.0,
                    "blocked": 0.0,
                    "idle": 0.0,
                }
            )
        groups.append(group)
    queues = [deque() for _ in capacities]
    peaks = [0] * len(queues)
    queue_area = [0.0] * len(queues)
    rw_queue = deque()
    rw = {"state": "idle", "unit": None, "processing": 0.0, "blocked": 0.0, "idle": 0.0}
    rework = quality.get("rework") if quality else None
    events = []
    snapshots = []
    calendar = []
    now = 0.0
    released = 0
    accepted = []
    scrapped = []
    history = {}
    operator_time = [0.0] * count
    inspected = first_pass = rw_started = rw_passed = 0
    wip_area = 0

    def emit(worker, unit, event, result="pending"):
        item = history[unit]
        is_rw = worker is None
        station = "REWORK" if is_rw else stages[workers[worker]["stage"]]["id"]
        entry = dict(
            zip(
                FIELDS,
                [
                    config.get("run_id", "parallel_manual"),
                    config["model_version"],
                    config["scenario"],
                    unit,
                    station,
                    now,
                    event,
                    rw["state"] if is_rw else workers[worker]["state"],
                    result,
                    "",
                    1,
                    (
                        ("REWORK-1" if rw["state"] == "processing" else None)
                        if is_rw
                        else workers[worker]["operator"]
                    ),
                    "|".join(item["origins"]),
                    item["rework_count"],
                    "REWORK-1" if is_rw else workers[worker]["resource_id"],
                ],
            )
        )
        events.append(entry)

    def free_operator():
        busy = {w["operator"] for w in workers if w["operator"] is not None}
        return next((o for o in range(count) if o not in busy), None)

    def start(index, unit):
        worker = workers[index]
        worker.update(state="processing", unit=unit, operator=free_operator())
        if worker["operator"] is None:
            raise RuntimeError("No operator for processing")
        emit(index, unit, "started")
        duration = sample_duration(config, timing, stages[worker["stage"]], unit)
        heapq.heappush(calendar, (now + duration, index, unit))

    def transfer(source, unit, target):
        if not queues[target - 1] and now < horizon and free_operator() is not None:
            idle = next(
                (i for i in groups[target] if workers[i]["state"] == "idle"), None
            )
            if idle is not None:
                emit(source, unit, "transferred", "pass")
                emit(idle, unit, "entered")
                start(idle, unit)
                return True
        if len(queues[target - 1]) < capacities[target - 1]:
            queues[target - 1].append(unit)
            peaks[target - 1] = max(peaks[target - 1], len(queues[target - 1]))
            emit(source, unit, "buffer_enqueued")
            return True
        return False

    def settle():
        nonlocal released, rw_started
        changed = True
        while changed:
            changed = False
            for stage in range(n - 1, -1, -1):
                for index in groups[stage]:
                    worker = workers[index]
                    if (
                        stage
                        and worker["state"] == "idle"
                        and queues[stage - 1]
                        and now < horizon
                        and free_operator() is not None
                    ):
                        unit = queues[stage - 1].popleft()
                        emit(index, unit, "buffer_dequeued")
                        start(index, unit)
                        changed = True
                    if worker["state"] != "blocked":
                        continue
                    unit = worker["unit"]
                    if stage == n - 1:
                        accepted.append((unit, now))
                        emit(index, unit, "accepted", "pass")
                    elif not transfer(index, unit, stage + 1):
                        continue
                    worker.update(state="idle", unit=None)
                    changed = True
            if rw["state"] == "blocked" and transfer(None, rw["unit"], n - 1):
                rw.update(state="idle", unit=None)
                changed = True
            if rw["state"] == "idle" and rw_queue and now < horizon:
                unit = rw_queue.popleft()
                rw.update(state="processing", unit=unit)
                history[unit]["rework_count"] = 1
                rw_started += 1
                emit(None, unit, "rework_started")
                heapq.heappush(
                    calendar, (now + rework["duration_s"], len(workers), unit)
                )
                changed = True
            first = groups[0][0]
            if (
                workers[first]["state"] == "idle"
                and now < horizon
                and free_operator() is not None
            ):
                released += 1
                unit = f"UNIT-{released:06d}"
                history[unit] = {
                    "entry": now,
                    "origins": [],
                    "defective": False,
                    "rework_count": 0,
                }
                emit(first, unit, "released")
                start(first, unit)
                changed = True

    def snapshot():
        snapshots.append(
            {
                "timestamp_s": now,
                "queue_lengths": [len(q) for q in queues],
                "station_units": [w["unit"] for w in workers],
                "station_states": [w["state"] for w in workers],
                "station_operators": [w["operator"] for w in workers],
                "released_units": released,
                "accepted_units": len(accepted),
                "scrapped_units": len(scrapped),
                "rework_queue_length": len(rw_queue),
                "rework_unit": rw["unit"],
            }
        )

    def advance(target):
        nonlocal now, wip_area
        dt = target - now
        for worker in workers:
            worker[worker["state"]] += dt
            if worker["operator"] is not None:
                operator_time[worker["operator"]] += dt
        rw[rw["state"]] += dt
        for i, q in enumerate(queues):
            queue_area[i] += len(q) * dt
        wip_area += (released - len(accepted) - len(scrapped)) * dt
        now = target

    settle()
    snapshot()
    while calendar and calendar[0][0] <= horizon:
        advance(calendar[0][0])
        while calendar and calendar[0][0] == now:
            _, index, unit = heapq.heappop(calendar)
            if index == len(workers):
                if outcome(
                    config, unit, "rework", "REWORK", rework["success_probability"]
                ):
                    rw_passed += 1
                    history[unit]["defective"] = False
                    emit(None, unit, "rework_passed", "pass")
                    rw["state"] = "blocked"
                else:
                    emit(None, unit, "scrapped", "fail")
                    scrapped.append((unit, now))
                    rw.update(state="idle", unit=None)
                continue
            worker = workers[index]
            stage = worker["stage"]
            worker["state"] = "blocked"
            emit(index, unit, "completed")
            worker["operator"] = None
            if quality:
                p = quality.get("defect_probabilities", {}).get(stages[stage]["id"], 0)
                if outcome(config, unit, "defect", stages[stage]["id"], p):
                    history[unit]["origins"].append(stages[stage]["id"])
                    history[unit]["defective"] = True
                    emit(index, unit, "defect_created")
                if stage == n - 2:
                    inspected += 1
                    if history[unit]["defective"]:
                        emit(index, unit, "rejected", "fail")
                        if rework:
                            rw_queue.append(unit)
                        else:
                            scrapped.append((unit, now))
                            emit(index, unit, "scrapped", "fail")
                        worker.update(state="idle", unit=None)
                    else:
                        first_pass += 1
                        emit(index, unit, "inspection_passed", "pass")
        settle()
        snapshot()
    if now < horizon:
        if not calendar and released > len(accepted) + len(scrapped):
            raise RuntimeError("Parallel-line deadlock")
        advance(horizon)
        snapshot()
    unfinished = (
        sum(w["unit"] is not None for w in workers)
        + sum(map(len, queues))
        + len(rw_queue)
        + int(rw["unit"] is not None)
    )
    if released != len(accepted) + len(scrapped) + unfinished:
        raise RuntimeError("Parallel unit conservation failed")
    paid = (count + int(rework is not None)) * config["shift_duration_s"] / 3600
    summary = {
        "model": "parallel_manual_finite_buffers",
        "model_version": config["model_version"],
        "scenario": config["scenario"],
        "run_id": config.get("run_id", "parallel_manual"),
        "seed": config.get("seed"),
        "input_source": config["input_source"],
        "production_window_s": horizon,
        "released_units": released,
        "accepted_units": len(accepted),
        "scrapped_units": len(scrapped),
        "unfinished_units": unfinished,
        "paid_labor_hours": paid,
        "good_units_per_paid_labor_hour": len(accepted) / paid,
        "rework_started_units": rw_started,
        "rework_passed_units": rw_passed,
        "first_inspections": inspected,
        "first_pass_units": first_pass,
        "first_pass_yield": first_pass / inspected if inspected else None,
        "accepted_after_rework": sum(
            history[u]["rework_count"] > 0 for u, _ in accepted
        ),
        "demand_met": len(accepted) >= config["target_good_units"],
        "target_good_units": config["target_good_units"],
        "first_completion_s": accepted[0][1] if accepted else None,
        "mean_accepted_lead_time_s": (
            sum(t - history[u]["entry"] for u, t in accepted) / len(accepted)
            if accepted
            else None
        ),
        "time_weighted_mean_wip": wip_area / horizon,
        "operator_count": count,
        "parallel_servers": servers,
        "operators": [
            {"operator_id": i, "productive_time_s": t}
            for i, t in enumerate(operator_time)
        ],
        "stations": [
            {
                "station_id": w["resource_id"],
                "operation_id": stages[w["stage"]]["id"],
                "productive_time_s": w["processing"],
                "blocked_time_s": w["blocked"],
                "starved_time_s": w["idle"],
                "fault_time_s": 0,
                "waiting_for_operator_time_s": 0,
            }
            for w in workers
        ],
        "buffers": [
            {
                "capacity": c,
                "peak_waiting_units": peaks[i],
                "final_waiting_units": len(queues[i]),
                "time_weighted_mean_waiting_units": queue_area[i] / horizon,
            }
            for i, c in enumerate(capacities)
        ],
        "assumptions": [
            "Fully attended manual operations; no equipment failures",
            "Actual parallel station resources; each occupies one shared operator while processing",
            "FIFO by buffer arrival; parallel outputs may complete out of input order",
            "Downstream-first dispatch, blocking after service, zero travel and transfers",
            "Idle resource time combines input starvation and unavailable operator",
            "One separate paid rework operator when enabled; unlimited rework input queue",
        ],
    }
    return events, summary, snapshots
