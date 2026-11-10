"""Per-unit S3 controller/equipment cycle adapter; explicit time scaling, no hardware claim."""

import sys
from functools import lru_cache
from pathlib import Path
from quality import outcome, probability

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/cell"))
from s3_demo import run_demo


@lru_cache(maxsize=1)
def normal_duration():
    return run_demo("normal")["duration_s"]


def validate_adapter(config):
    linked = [s for s in config["stations"] if s.get("cell_adapter") is not None]
    if len(linked) > 1:
        raise ValueError("Only one S3 cell adapter supported")
    for station in linked:
        adapter = station["cell_adapter"]
        if station["id"] != "S3" or not isinstance(adapter, dict):
            raise ValueError("Cell adapter must be an S3 settings object")
        fail = adapter.get("failed_result_probability", 0)
        fault = adapter.get("fault_probability", 0)
        if not probability(fail) or not probability(fault) or fail + fault > 1:
            raise ValueError("Invalid adapter outcome probabilities")
        if station.get("reliability"):
            raise ValueError(
                "Linked S3 cannot also have an independent breakdown clock"
            )
        if not config.get("quality"):
            raise ValueError("Linked S3 requires downstream quality handling")
        if config["quality"].get("defect_probabilities", {}).get("S3", 0):
            raise ValueError("S3 defects must originate from the linked cell only")
        if type(config.get("seed")) is not int:
            raise ValueError("Cell adapter requires a seed")
    return bool(linked)


def execute_cycle(config, station, unit, nominal_duration):
    settings = station["cell_adapter"]
    p_fail = settings.get("failed_result_probability", 0)
    p_fault = settings.get("fault_probability", 0)
    # Conditional independent draws realize mutually exclusive normal/fail/fault probabilities.
    if outcome(config, unit, "adapter_category", "S3", p_fault):
        demo = "permit_removed"
    elif outcome(
        config,
        unit,
        "adapter_fail_given_no_fault",
        "S3",
        p_fail / (1 - p_fault) if p_fault < 1 else 0,
    ):
        demo = "failed_process"
    else:
        demo = "normal"
    trace = run_demo(demo, unit_id=unit)
    if not trace["passed"]:
        raise RuntimeError("Linked cell commissioning checks failed")
    duration = nominal_duration * trace["duration_s"] / normal_duration()
    return {
        "unit_id": unit,
        "demo": demo,
        "outcome": (
            "quarantined"
            if demo == "permit_removed"
            else "fail" if demo == "failed_process" else "pass"
        ),
        "cell_duration_s": trace["duration_s"],
        "line_duration_s": duration,
        "time_scale": nominal_duration / normal_duration(),
        "trace": trace,
    }
