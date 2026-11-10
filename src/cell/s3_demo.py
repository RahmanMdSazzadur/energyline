"""Software-in-the-loop commissioning harness. Equipment and controller share I/O only."""

import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src/controls"), str(ROOT / "src/equipment_model")]
from s3_controller import S3Controller, STATES
from s3_equipment import S3Equipment

DEMOS = {
    "normal": ("Normal cycle", None),
    "missing_tray": ("Missing tray", "MISSING_TRAY"),
    "missing_cover": ("Missing cover", "MISSING_COVER"),
    "clamp_timeout": ("Clamp confirmation timeout", "CLAMP_TIMEOUT"),
    "process_timeout": ("Process timeout", "PROCESS_TIMEOUT"),
    "failed_process": ("Failed result → rework", None),
    "downstream_blocked": ("Downstream unavailable", None),
    "permit_removed": ("Permit removed in process", "PERMIT_REMOVED"),
    "communication_loss": ("Communication interruption", "COMMUNICATION_LOSS"),
    "restart_occupied": ("Restart with occupied fixture", "RESTART_OCCUPIED"),
    "duplicate_signals": ("Repeated start and done signals", None),
}


def run_demo(name, unit_id="S3-DEMO-0001"):
    if not isinstance(name, str) or name not in DEMOS:
        raise ValueError("Unknown cell demonstration")
    plant = S3Equipment()
    controller = S3Controller()
    timeline = []
    external = []
    archived = []
    fault_at = None
    injected = False
    reset_done = False
    recovery_done = False
    loaded = False
    for step in range(321):
        now = round(step * 0.05, 4)
        commands = {}
        if step == 2:
            plant.load(
                unit_id, cover=name != "missing_cover", tray=name != "missing_tray"
            )
            loaded = True
            external.append({"timestamp_s": now, "event_type": "operator_loaded_unit"})
            plant.clamp_jammed = name == "clamp_timeout"
            plant.process_jammed = name == "process_timeout"
            plant.force_process_fail = name == "failed_process"
            plant.downstream_ready = name != "downstream_blocked"
        if step == 3:
            commands["start_request"] = True
        if name == "duplicate_signals" and 3 <= step < 120:
            commands["start_request"] = True
        if name == "downstream_blocked" and now >= 6:
            plant.downstream_ready = True
        if (
            controller.state == "PROCESSING"
            and now - controller.since >= 0.3
            and not injected
        ):
            if name == "permit_removed":
                plant.safety_permit = False
                injected = True
            if name == "communication_loss":
                plant.communication_ok = False
                injected = True
            if name == "restart_occupied":
                journal = json.loads(json.dumps(controller.journal))
                archived.extend(controller.events)
                controller = S3Controller(journal)
                injected = True
                external.append(
                    {
                        "timestamp_s": now,
                        "event_type": "controller_restarted_from_serialized_journal",
                    }
                )
        if controller.state == "FAULT" and fault_at is None:
            fault_at = now
        if fault_at is not None:
            if now >= fault_at + 0.5:
                plant.clamp_jammed = plant.process_jammed = False
                plant.safety_permit = plant.communication_ok = True
            if now >= fault_at + 0.8 and not reset_done:
                commands["reset_request"] = True
                reset_done = True
            if now >= fault_at + 1.5 and not recovery_done:
                commands["recover_request"] = True
                recovery_done = True
            if (
                controller.state == "RECOVERY_RELEASE"
                and plant.clamp_position <= 0
                and plant.part_present
            ):
                plant.remove()
                external.append(
                    {
                        "timestamp_s": now,
                        "event_type": "operator_removed_quarantined_unit",
                    }
                )
        outputs = controller.tick(now, plant.signals(), commands)
        timeline.append(
            {
                "timestamp_s": now,
                "controller_state": controller.state,
                "fault_code": controller.fault_code,
                "result": controller.result,
                "signals": plant.signals(),
                "outputs": outputs,
                "equipment": {
                    "clamp_position": round(plant.clamp_position, 4),
                    "process_fraction": min(1, round(plant.process_elapsed / 2, 4)),
                    "process_running": plant.process_running,
                },
                "commands": commands,
            }
        )
        plant.step(0.05, outputs)
        if (
            loaded
            and controller.state == "IDLE"
            and now > 1
            and (controller.journal["units"] or fault_at is not None)
        ):
            break
    events = archived + controller.events
    completed = [e for e in events if e["event_type"] == "completed"]
    faults = [e for e in events if e["event_type"] == "fault"]
    expected = DEMOS[name][1]
    checks = {
        "expected_fault": (
            any(e["fault_code"] == expected for e in faults) if expected else not faults
        ),
        "no_duplicate_completion": len({e["unit_id"] for e in completed})
        == len(completed),
        "correct_completion_count": len(completed) == (0 if expected else 1),
        "returned_to_idle": controller.state == "IDLE",
        "single_process_command": plant.process_starts <= 1,
        "fault_outputs_inhibited": all(
            not t["outputs"]["process_start"]
            and not t["outputs"]["process_enable"]
            and not t["outputs"]["motion_enable"]
            and not t["outputs"]["transfer_request"]
            for t in timeline
            if t["controller_state"] == "FAULT"
        ),
        "reset_did_not_restart_motion": all(
            t["controller_state"] == "RECOVERY"
            and not t["outputs"]["process_start"]
            and not t["outputs"]["process_enable"]
            and not t["outputs"]["motion_enable"]
            and not t["outputs"]["transfer_request"]
            for t in timeline
            if t["commands"].get("reset_request")
        ),
        "failed_result_routed_to_rework": name != "failed_process"
        or plant.transfers == [{"unit_id": unit_id, "route": "rework"}],
        "downstream_result_retained": name != "downstream_blocked"
        or all(
            t["result"] == "pass"
            for t in timeline
            if t["controller_state"] == "WAIT_TRANSFER"
        ),
    }
    return {
        "demo": name,
        "label": DEMOS[name][0],
        "model_version": "0.2.0",
        "input_source": "synthetic_equipment_model",
        "dt_s": 0.05,
        "duration_s": timeline[-1]["timestamp_s"],
        "expected_fault": expected,
        "checks": checks,
        "passed": all(checks.values()),
        "timeline": timeline,
        "events": events,
        "external_actions": external,
        "journal": controller.journal,
        "transfers": plant.transfers,
        "process_starts": plant.process_starts,
        "states": STATES,
        "limitations": [
            "Accelerated illustrative equipment timings; not the 70-second production estimate",
            "Simulated permit only; no certified safety function or real hardware",
            "Scripted fault injection and recovery; browser shows recorded simulation playback",
            "Restart reloads a serialized software journal; not power-loss hardware validation",
            "All faulted in-process units quarantined; reset never resumes uncertain processing",
        ],
    }


def main():
    destination = ROOT / "results/s3_commissioning"
    destination.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in DEMOS:
        result = run_demo(name)
        (destination / f"{name}.json").write_text(json.dumps(result, indent=2) + "\n")
        rows.append(
            {
                "test_id": name,
                "expected_response": DEMOS[name][1]
                or "Single completion; correct routing",
                "observed_faults": "|".join(
                    e["fault_code"]
                    for e in result["events"]
                    if e["event_type"] == "fault"
                ),
                "passed": result["passed"],
                "evidence_file": f"{name}.json",
            }
        )
        print(name, "PASS" if result["passed"] else "FAIL")
    with (destination / "commissioning.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    hashes = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for folder in ("controls", "equipment_model", "cell")
        for p in (ROOT / "src" / folder).glob("*.py")
    }
    (destination / "manifest.json").write_text(
        json.dumps(
            {
                "model_version": "0.2.0",
                "source_sha256": hashes,
                "test_count": len(rows),
                "passed": all(r["passed"] for r in rows),
            },
            indent=2,
        )
        + "\n"
    )
    if not all(r["passed"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
