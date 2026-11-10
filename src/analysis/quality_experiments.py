"""Synthetic defect and one-attempt rework comparison under moderate S2/S3 failures."""

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
    base = json.loads((ROOT / "configs/quality_baseline.json").read_text())
    destination = ROOT / "results/quality"
    destination.mkdir(parents=True, exist_ok=True)
    profiles = [
        ("no_defects", {}, None),
        ("defects_scrapped", {"S2": 0.02, "S3": 0.03}, None),
        (
            "base_rework",
            {"S2": 0.02, "S3": 0.03},
            {"duration_s": 180, "success_probability": 0.8},
        ),
        (
            "high_defects_rework",
            {"S2": 0.08, "S3": 0.10},
            {"duration_s": 180, "success_probability": 0.8},
        ),
    ]
    configs = []
    rows = []
    aggregates = []
    for name, defects, rework in profiles:
        config = copy.deepcopy(base)
        config.update(
            scenario=name,
            quality={
                "inspection_station": "S4",
                "defect_probabilities": defects,
                "rework": rework,
            },
        )
        configs.append(copy.deepcopy(config))
        case_rows = []
        for rep in range(100):
            config.update(seed=20261209 + rep, run_id=f"{name}_rep_{rep+1:03d}")
            events, result, _ = simulate(config)
            row = {
                key: result[key]
                for key in [
                    "run_id",
                    "seed",
                    "accepted_units",
                    "scrapped_units",
                    "unfinished_units",
                    "first_pass_yield",
                    "rework_started_units",
                    "accepted_after_rework",
                    "paid_labor_hours",
                    "good_units_per_paid_labor_hour",
                ]
            }
            row.update(
                scenario=name,
                first_inspections=result["first_inspections"],
                first_pass_units=result["first_pass_units"],
            )
            rows.append(row)
            case_rows.append(row)
            if rep == 0:
                folder = destination / name
                folder.mkdir(exist_ok=True)
                (folder / "config.json").write_text(json.dumps(config, indent=2) + "\n")
                (folder / "summary.json").write_text(
                    json.dumps(result, indent=2) + "\n"
                )
                with (folder / "events.csv").open("w", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=FIELDS)
                    writer.writeheader()
                    writer.writerows(events)
        outputs = [r["accepted_units"] for r in case_rows]
        successes = sum(x >= 240 for x in outputs)
        low, high = wilson_interval(successes, 100)
        aggregates.append(
            {
                "scenario": name,
                "replications": 100,
                "mean_good_units": statistics.mean(outputs),
                "minimum": min(outputs),
                "maximum": max(outputs),
                "pooled_first_pass_yield": sum(r["first_pass_units"] for r in case_rows)
                / sum(r["first_inspections"] for r in case_rows),
                "mean_scrapped_units": statistics.mean(
                    r["scrapped_units"] for r in case_rows
                ),
                "mean_accepted_after_rework": statistics.mean(
                    r["accepted_after_rework"] for r in case_rows
                ),
                "mean_good_units_per_paid_labor_hour": statistics.mean(
                    r["good_units_per_paid_labor_hour"] for r in case_rows
                ),
                "successful_shifts": successes,
                "wilson_95_lower": low,
                "wilson_95_upper": high,
            }
        )
        print(
            f'{name}: mean {statistics.mean(outputs):.1f}, demand {successes}/100, FPY {aggregates[-1]["pooled_first_pass_yield"]:.1%}, scrap {aggregates[-1]["mean_scrapped_units"]:.1f}'
        )
    for name, data in [("runs", rows), ("comparison", aggregates)]:
        with (destination / f"{name}.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    (destination / "manifest.json").write_text(
        json.dumps(
            {
                "model_version": "0.1.7",
                "cases": configs,
                "replications_per_case": 100,
                "seed_rule": "20261209 plus zero-based replication",
                "quality": "Independent defect-origin draws at process completion; perfect detection at S4",
                "rework": "One dedicated offline operator; fixed repair/reinspection duration; unlimited FIFO input",
                "routing": "Pass rework rejoins finite buffer before S5; full output blocks rework resource; fail is scrap",
                "metrics": "FPY pooled across first inspections; accepted output only after S5, including recovered units",
                "limitations": [
                    "All inputs synthetic; no measured process or reliability evidence",
                    "No inspection false positives/negatives, travel or transfer labor",
                    "Rework labor adds one paid 8-hour operator; output comparisons are not equal-labor comparisons",
                    "Unfinished rework stays WIP, excluded from accepted output and scrap",
                    "No costs or equipment investment recommendation yet",
                ],
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
