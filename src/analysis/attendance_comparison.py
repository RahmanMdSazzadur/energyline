"""Hypothetical attended/unattended timing sensitivity; not measured labor savings."""

import copy
import csv
import json
import sys
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src/simulation"), str(ROOT / "src/analysis")]
from finite_buffers import simulate
from variability_experiments import wilson_interval


def main():
    base = json.loads((ROOT / "configs/scenarios/D_faster_s2_s3.json").read_text())
    folder = ROOT / "results/attendance"
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    aggregates = []
    configs = []
    for fraction in (1.0, 0.5, 0.25):
        for count in (2, 3, 4, 5):
            config = copy.deepcopy(base)
            config.update(
                operator_count=count,
                model_version="0.1.5",
                scenario=f"faster_s2_s3_attended_{fraction}_ops_{count}",
            )
            for station in config["stations"]:
                if station["id"] in ("S2", "S3"):
                    station["operator_attended_fraction"] = fraction
            configs.append(copy.deepcopy(config))
            outputs = []
            for rep in range(30):
                config.update(
                    seed=base["seed"] + rep,
                    run_id=f"{config['scenario']}_rep_{rep+1:03d}",
                )
                _, result, _ = simulate(config)
                outputs.append(result["accepted_units"])
                rows.append(
                    {
                        "run_id": config["run_id"],
                        "seed": config["seed"],
                        "operator_count": count,
                        "s2_s3_attended_fraction": fraction,
                        "accepted_units": result["accepted_units"],
                        "unfinished_units": result["unfinished_units"],
                        "good_units_per_paid_labor_hour": result[
                            "good_units_per_paid_labor_hour"
                        ],
                    }
                )
            successes = sum(x >= 240 for x in outputs)
            low, high = wilson_interval(successes, 30)
            aggregates.append(
                {
                    "operator_count": count,
                    "s2_s3_attended_fraction": fraction,
                    "mean_good_units": statistics.mean(outputs),
                    "minimum": min(outputs),
                    "maximum": max(outputs),
                    "successful_shifts": successes,
                    "replications": 30,
                    "wilson_95_lower": low,
                    "wilson_95_upper": high,
                }
            )
            print(
                f"{count} operators, S2/S3 attended {fraction:.0%}: mean {statistics.mean(outputs):.1f}, range {min(outputs)}–{max(outputs)}, demand {successes}/30"
            )
    for name, data in [("runs", rows), ("comparison", aggregates)]:
        with (folder / f"{name}.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    (folder / "manifest.json").write_text(
        json.dumps(
            {
                "model_version": "0.1.5",
                "cases": configs,
                "seed_rule": "Base seed plus replication index; 30 paired shifts per case",
                "limitations": [
                    "Attendance fractions are synthetic sensitivity inputs",
                    "Operator attends initial cycle fraction only; no return for unloading",
                    "No travel, downtime, quality losses or equipment costs",
                    "Same faster station times in all cases; no claim of measured labor savings",
                ],
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
