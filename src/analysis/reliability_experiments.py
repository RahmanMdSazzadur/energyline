"""Synthetic S2/S3 reliability sensitivity with independent processing-time failure clocks."""

import copy
import csv
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src/simulation"), str(ROOT / "src/analysis")]
from finite_buffers import FIELDS, simulate
from variability_experiments import wilson_interval


def main():
    base = json.loads((ROOT / "configs/scenarios/D_faster_s2_s3.json").read_text())
    folder = ROOT / "results/reliability"
    folder.mkdir(parents=True, exist_ok=True)
    profiles = [
        ("no_failures", None),
        ("mild", {"mtbf_s": 3600, "repair_mean_s": 120}),
        ("moderate", {"mtbf_s": 1800, "repair_mean_s": 180}),
        ("severe", {"mtbf_s": 900, "repair_mean_s": 300}),
    ]
    configs = []
    rows = []
    aggregates = []
    for name, settings in profiles:
        for count in (3, 4):
            case = copy.deepcopy(base)
            case.update(
                model_version="0.1.6",
                operator_count=count,
                scenario=f"{name}_ops_{count}",
            )
            for station in case["stations"]:
                if station["id"] in ("S2", "S3"):
                    station["operator_attended_fraction"] = 0.5
                    if settings is not None:
                        station["reliability"] = copy.deepcopy(settings)
            configs.append(copy.deepcopy(case))
            outputs = []
            for rep in range(100):
                case.update(
                    seed=20261209 + rep, run_id=f"{name}_ops_{count}_rep_{rep+1:03d}"
                )
                events, result, _ = simulate(case)
                outputs.append(result["accepted_units"])
                rows.append(
                    {
                        "run_id": case["run_id"],
                        "seed": case["seed"],
                        "profile": name,
                        "operator_count": count,
                        "accepted_units": result["accepted_units"],
                        "unfinished_units": result["unfinished_units"],
                        "failures": sum(s["failure_count"] for s in result["stations"]),
                        "summed_station_fault_time_s": sum(
                            s["fault_time_s"] for s in result["stations"]
                        ),
                    }
                )
                if rep == 0:
                    path = folder / f"{name}_ops_{count}"
                    path.mkdir(exist_ok=True)
                    (path / "summary.json").write_text(
                        json.dumps(result, indent=2) + "\n"
                    )
                    (path / "config.json").write_text(json.dumps(case, indent=2) + "\n")
                    with (path / "events.csv").open("w", newline="") as handle:
                        writer = csv.DictWriter(handle, fieldnames=FIELDS)
                        writer.writeheader()
                        writer.writerows(events)
            successes = sum(x >= 240 for x in outputs)
            lower, upper = wilson_interval(successes, 100)
            aggregates.append(
                {
                    "profile": name,
                    "operator_count": count,
                    "replications": 100,
                    "mean_good_units": statistics.mean(outputs),
                    "minimum": min(outputs),
                    "maximum": max(outputs),
                    "successful_shifts": successes,
                    "observed_demand_attainment": successes / 100,
                    "wilson_95_lower": lower,
                    "wilson_95_upper": upper,
                }
            )
            print(
                f"{name}, {count} operators: mean {statistics.mean(outputs):.1f}, range {min(outputs)}–{max(outputs)}, demand {successes}/100"
            )
    for name, data in [("runs", rows), ("comparison", aggregates)]:
        with (folder / f"{name}.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    (folder / "manifest.json").write_text(
        json.dumps(
            {
                "model_version": "0.1.6",
                "cases": configs,
                "replications_per_case": 100,
                "seeds": list(range(20261209, 20261309)),
                "clock": "Cumulative station processing time only; paused during idle, blocking, repair and operator waits",
                "distributions": "Exponential uptime and repair; independent namespaces from process times",
                "interruption": "Resume remaining process and attendance; operator released on failure and reacquired if needed",
                "limitations": [
                    "All reliability values are synthetic sensitivity inputs, not equipment specifications",
                    "Only S2 and S3 fail; all other stations remain failure-free",
                    "Repair has unlimited external maintenance resources and needs no production operator",
                    "No scrap, quality loss, rework, walking or unloading tasks",
                    "Summed station fault time can overlap; it is not line downtime",
                    "Confidence intervals quantify simulation sampling uncertainty, not input/model validity",
                ],
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
