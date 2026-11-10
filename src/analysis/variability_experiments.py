"""Repeated empty-start shift experiments; all timing inputs are synthetic."""

import copy
import csv
import json
import math
import platform
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/simulation"))
from finite_buffers import simulate


def wilson_interval(successes, trials):
    if type(trials) is not int or trials <= 0 or not 0 <= successes <= trials:
        raise ValueError("Invalid binomial observations")
    z = statistics.NormalDist().inv_cdf(0.975)
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    half = (
        z
        * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials))
        / denominator
    )
    return max(0, center - half), min(1, center + half)


def percentile(values, probability):
    values = sorted(values)
    position = (len(values) - 1) * probability
    low, high = math.floor(position), math.ceil(position)
    return values[low] + (values[high] - values[low]) * (position - low)


def main():
    config = json.loads((ROOT / "configs/variable_times.json").read_text())
    destination = ROOT / "results/variability"
    destination.mkdir(parents=True, exist_ok=True)
    replications = 30
    base_seed = config["seed"]
    rows, aggregates, cases = [], [], []
    for width in (0.2, 0.4):
        for operators in (1, 2, 3, 5):
            case = copy.deepcopy(config)
            case.update(
                operator_count=operators,
                scenario=f"manual_ops_{operators}_variation_{int(width*100)}",
            )
            case["processing_time"]["relative_half_width"] = width
            cases.append(copy.deepcopy(case))
            case_rows = []
            for replication in range(replications):
                case.update(
                    seed=base_seed + replication,
                    run_id=f"{case['scenario']}_rep_{replication+1:03d}",
                )
                _, summary, _ = simulate(case)
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
                        "demand_met",
                        "time_weighted_mean_wip",
                        "mean_accepted_lead_time_s",
                        "good_units_per_paid_labor_hour",
                    ]
                }
                row.update(replication=replication + 1, relative_half_width=width)
                rows.append(row)
                case_rows.append(row)
            outputs = [r["accepted_units"] for r in case_rows]
            successes = sum(r["demand_met"] for r in case_rows)
            lower, upper = wilson_interval(successes, replications)
            aggregate = dict(
                scenario=case["scenario"],
                operator_count=operators,
                relative_half_width=width,
                replications=replications,
                mean_good_units=statistics.mean(outputs),
                sample_sd=statistics.stdev(outputs),
                minimum=min(outputs),
                maximum=max(outputs),
                p05=percentile(outputs, 0.05),
                median=statistics.median(outputs),
                p95=percentile(outputs, 0.95),
                successful_shifts=successes,
                observed_demand_attainment=successes / replications,
                demand_attainment_wilson_95_lower=lower,
                demand_attainment_wilson_95_upper=upper,
            )
            aggregates.append(aggregate)
            print(
                f"{operators} operators, +/-{width:.0%}: mean {aggregate['mean_good_units']:.1f}, range {min(outputs)}–{max(outputs)}, met demand {successes}/{replications}"
            )
    for name, data in [("runs", rows), ("comparison", aggregates)]:
        with (destination / f"{name}.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    manifest = {
        "model_version": config["model_version"],
        "python_version": platform.python_version(),
        "replications_per_case": replications,
        "seeds": list(range(base_seed, base_seed + replications)),
        "cases": cases,
        "input_source": "synthetic_assumption",
        "pairing": "Same seed/unit/station processing draw across cases; not all cases process the same units",
        "interval": "Two-sided 95% Wilson binomial interval for demand attainment",
        "percentiles": "Empirical output percentiles with linear interpolation; not confidence intervals",
        "limitations": [
            "No failures, quality losses, walking or skill differences",
            "No empirical timing validation; no industrial throughput claim",
            "30 replications per case is an initial experiment, not a 90% reliability certification",
        ],
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
