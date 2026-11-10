"""Controlled comparison of hypothetical process improvements; no investment claim."""

import copy
import csv
import hashlib
import json
import platform
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src/simulation"), str(ROOT / "src/analysis")]
from finite_buffers import simulate
from variability_experiments import percentile, wilson_interval


def main():
    destination = ROOT / "results/scenarios"
    destination.mkdir(parents=True, exist_ok=True)
    replications = 30
    rows, aggregates, cases, evidence = [], [], [], []
    for path in sorted((ROOT / "configs/scenarios").glob("*.json")):
        base = json.loads(path.read_text())
        for operators in (3, 5):
            config = copy.deepcopy(base)
            config.update(
                operator_count=operators, scenario=f"{base['scenario']}_ops_{operators}"
            )
            cases.append(copy.deepcopy(config))
            outputs = []
            for rep in range(replications):
                config.update(
                    seed=base["seed"] + rep,
                    run_id=f"{config['scenario']}_rep_{rep+1:03d}",
                )
                _, summary, _ = simulate(config)
                outputs.append(summary["accepted_units"])
                row = {
                    key: summary[key]
                    for key in [
                        "run_id",
                        "model_version",
                        "scenario",
                        "seed",
                        "operator_count",
                        "accepted_units",
                        "released_units",
                        "unfinished_units",
                        "time_weighted_mean_wip",
                        "mean_accepted_lead_time_s",
                        "good_units_per_paid_labor_hour",
                    ]
                }
                row["replication"] = rep + 1
                rows.append(row)
                if rep == 0:
                    evidence.append(
                        {
                            "scenario": config["scenario"],
                            "seed": config["seed"],
                            "stations": summary["stations"],
                            "buffers": summary["buffers"],
                        }
                    )
            for target in (160, 240, 320):
                successes = sum(value >= target for value in outputs)
                lower, upper = wilson_interval(successes, replications)
                aggregates.append(
                    dict(
                        scenario=config["scenario"],
                        operator_count=operators,
                        target_good_units=target,
                        replications=replications,
                        mean_good_units=statistics.mean(outputs),
                        sample_sd=statistics.stdev(outputs),
                        minimum=min(outputs),
                        maximum=max(outputs),
                        p05=percentile(outputs, 0.05),
                        p95=percentile(outputs, 0.95),
                        successful_shifts=successes,
                        observed_demand_attainment=successes / replications,
                        wilson_95_lower=lower,
                        wilson_95_upper=upper,
                    )
                )
            print(
                f"{config['scenario']}: mean {statistics.mean(outputs):.1f}, range {min(outputs)}–{max(outputs)}, target 240 met {sum(x>=240 for x in outputs)}/30"
            )
    for name, data in [("runs", rows), ("comparison", aggregates)]:
        with (destination / f"{name}.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    # Paired seed comparison to manual baseline at the same staffing level.
    paired = []
    for case in cases:
        baseline = f"A_manual_ops_{case['operator_count']}"
        reference = {
            r["seed"]: r["accepted_units"] for r in rows if r["scenario"] == baseline
        }
        differences = [
            r["accepted_units"] - reference[r["seed"]]
            for r in rows
            if r["scenario"] == case["scenario"]
        ]
        paired.append(
            {
                "scenario": case["scenario"],
                "baseline": baseline,
                "paired_shifts": replications,
                "mean_output_difference": statistics.mean(differences),
                "minimum_difference": min(differences),
                "maximum_difference": max(differences),
            }
        )
    (destination / "paired_differences.json").write_text(
        json.dumps(paired, indent=2) + "\n"
    )
    (destination / "first_replication_diagnostics.json").write_text(
        json.dumps(evidence, indent=2) + "\n"
    )
    source_hashes = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((ROOT / "src").rglob("*.py"))
    }
    manifest = {
        "python_version": platform.python_version(),
        "model_version": "0.1.4",
        "replications_per_case": replications,
        "total_shifts": len(rows),
        "cases": cases,
        "source_sha256": source_hashes,
        "input_source": "synthetic_assumption",
        "seed_rule": "base seed plus zero-based replication; common unit/station processing draws across cases",
        "demand_sensitivity": "160, 240 and 320 evaluated against the same shift output; release policy unchanged",
        "limitations": [
            "Unvalidated faster times; no equipment design or price evidence",
            "Operator held for entire cycle, including hypothetical faster process; no unattended overlap",
            "No failures, yield loss, rework, walking or costs",
            "Fixture alternative is a timing hypothesis, not a validated economic alternative",
            "30/30 success has a two-sided 95% Wilson lower bound below 90%; no reliability qualification",
            "Diagnostic station data is first replication only; not an aggregate bottleneck analysis",
        ],
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
