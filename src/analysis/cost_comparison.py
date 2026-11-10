"""Reproducible production and conversion-cost comparison; all inputs synthetic."""

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
from parallel_manual import simulate as simulate_parallel
from variability_experiments import wilson_interval
from economics import shift_cost


def build_cases():
    base = json.loads((ROOT / "configs/quality_baseline.json").read_text())
    definitions = [
        (
            "manual",
            "Manual line",
            3,
            {"S2": 120, "S3": 150},
            [],
            0,
            {
                "equipment": 0,
                "fixtures": 1500,
                "controls": 0,
                "integration": 0,
                "commissioning": 200,
                "training": 100,
                "installation": 0,
            },
            1,
        ),
        (
            "fixture",
            "Improved S3 fixture",
            3,
            {"S2": 120, "S3": 110},
            [],
            0,
            {
                "equipment": 0,
                "fixtures": 5000,
                "controls": 0,
                "integration": 500,
                "commissioning": 400,
                "training": 200,
                "installation": 200,
            },
            1.2,
        ),
        (
            "parallel_s3",
            "Two manual S3 fixtures",
            4,
            {"S2": 120, "S3": 150},
            [],
            0,
            {
                "equipment": 0,
                "fixtures": 3000,
                "controls": 0,
                "integration": 200,
                "commissioning": 300,
                "training": 150,
                "installation": 200,
            },
            1.4,
        ),
        (
            "s3",
            "Faster S3",
            3,
            {"S2": 120, "S3": 70},
            ["S3"],
            0.5,
            {
                "equipment": 18000,
                "fixtures": 2500,
                "controls": 3000,
                "integration": 4000,
                "commissioning": 2000,
                "training": 700,
                "installation": 1200,
            },
            3,
        ),
        (
            "s2_s3_3",
            "Faster S2/S3 · 3 operators",
            3,
            {"S2": 65, "S3": 70},
            ["S2", "S3"],
            0.5,
            {
                "equipment": 44000,
                "fixtures": 4500,
                "controls": 6000,
                "integration": 9000,
                "commissioning": 4000,
                "training": 1200,
                "installation": 2500,
            },
            5,
        ),
        (
            "s2_s3_4",
            "Faster S2/S3 · 4 operators",
            4,
            {"S2": 65, "S3": 70},
            ["S2", "S3"],
            0.5,
            {
                "equipment": 44000,
                "fixtures": 4500,
                "controls": 6000,
                "integration": 9000,
                "commissioning": 4000,
                "training": 1200,
                "installation": 2500,
            },
            5,
        ),
    ]
    cases = []
    for (
        key,
        label,
        operators,
        times,
        machines,
        fraction,
        components,
        power,
    ) in definitions:
        config = copy.deepcopy(base)
        config.update(model_version="0.2.1", scenario=key, operator_count=operators)
        for station in config["stations"]:
            station.pop("reliability", None)
            station.pop("operator_attended_fraction", None)
            station["mean_process_s"] = times.get(
                station["id"], station["mean_process_s"]
            )
            if station["id"] in machines:
                station.update(
                    operator_attended_fraction=fraction,
                    reliability={"mtbf_s": 1800, "repair_mean_s": 180},
                )
        if key == "parallel_s3":
            config["parallel_servers"] = [1, 1, 2, 1, 1]
        cases.append(
            {
                "id": key,
                "label": label,
                "config": config,
                "deployment": {"components_eur": components, "power_kw": power},
            }
        )
    return cases


def main():
    assumptions = json.loads((ROOT / "configs/economics/assumptions.json").read_text())
    cases = build_cases()
    folder = ROOT / "results/economics"
    folder.mkdir(parents=True, exist_ok=True)
    runs = []
    reports = []
    for case in cases:
        outputs = []
        costs = {k: [] for k in assumptions["cost_cases"]}
        summaries = []
        config = copy.deepcopy(case["config"])
        for rep in range(assumptions["replications_per_scenario"]):
            config.update(
                seed=assumptions["starting_seed"] + rep,
                run_id=f"economics_{case['id']}_{rep+1:03d}",
            )
            engine = simulate_parallel if config.get("parallel_servers") else simulate
            _, summary, _ = engine(config)
            summaries.append(summary)
            outputs.append(summary["accepted_units"])
            for name, inputs in assumptions["cost_cases"].items():
                cost = shift_cost(summary, assumptions, case["deployment"], inputs)
                costs[name].append(cost)
                runs.append(
                    {
                        "scenario": case["id"],
                        "cost_case": name,
                        "seed": config["seed"],
                        "accepted_units": summary["accepted_units"],
                        "scrapped_units": summary["scrapped_units"],
                        "paid_labor_hours": summary["paid_labor_hours"],
                        "shift_cost_eur": cost["shift_cost_eur"],
                        "conversion_cost_per_good_unit_eur": cost[
                            "conversion_cost_per_good_unit_eur"
                        ],
                    }
                )
        attainment = {}
        for target in (160, 240, 320):
            successes = sum(x >= target for x in outputs)
            lo, hi = wilson_interval(successes, len(outputs))
            attainment[str(target)] = {
                "successful_shifts": successes,
                "replications": len(outputs),
                "observed_probability": successes / len(outputs),
                "wilson_95_lower": lo,
                "wilson_95_upper": hi,
            }
        sensitivity = {}
        for name, values in costs.items():
            total = sum(v["shift_cost_eur"] for v in values)
            sensitivity[name] = {
                "mean_shift_cost_eur": total / len(values),
                "pooled_conversion_cost_per_good_unit_eur": (
                    total / sum(outputs) if sum(outputs) else None
                ),
                "mean_breakdown_eur": {
                    k: statistics.mean(v["breakdown_eur"][k] for v in values)
                    for k in values[0]["breakdown_eur"]
                },
                "deployment_total_eur": values[0]["deployment_total_eur"],
                "deployment_direct_eur": values[0]["deployment_direct_eur"],
                "deployment_contingency_eur": values[0]["deployment_contingency_eur"],
                "demand_capped_cost_per_unit_eur": {
                    str(target): (
                        total / sum(min(x, target) for x in outputs)
                        if sum(min(x, target) for x in outputs)
                        else None
                    )
                    for target in (160, 240, 320)
                },
            }
        reports.append(
            {
                "id": case["id"],
                "label": case["label"],
                "production_operators": config["operator_count"],
                "rework_operators": 1,
                "paid_labor_hours": summaries[0]["paid_labor_hours"],
                "replications": len(outputs),
                "mean_good_units": statistics.mean(outputs),
                "minimum": min(outputs),
                "maximum": max(outputs),
                "mean_scrapped_units": statistics.mean(
                    s["scrapped_units"] for s in summaries
                ),
                "demand_attainment": attainment,
                "cost_sensitivity": sensitivity,
                "payback_years": None,
                "payback_reason": costs["base"][0]["payback_reason"],
            }
        )
        print(
            f"{case['label']}: {statistics.mean(outputs):.1f} good/shift; base conversion cost EUR {sensitivity['base']['pooled_conversion_cost_per_good_unit_eur']:.2f}; target 240 {attainment['240']['successful_shifts']}/{len(outputs)}"
        )
    report = {
        "model_version": "0.2.1",
        "input_source": "synthetic_planning_assumptions",
        "currency": "EUR",
        "assumptions": assumptions,
        "cases": reports,
        "model_cases": cases,
        "total_simulated_shifts": len(cases) * assumptions["replications_per_scenario"],
        "python_version": platform.python_version(),
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for d in ("simulation", "analysis")
            for p in sorted((ROOT / "src" / d).glob("*.py"))
        },
        "limitations": [
            "All prices, station times, attendance, reliability and quality inputs are assumed, not quotes or measurements",
            "Conversion cost excludes good-unit BOM, buildings, overhead, taxes and finance",
            "All cases include one dedicated paid rework operator in addition to stated production staffing",
            "Manual stations have no modeled equipment failures; only proposed machine stations can fail",
            "Energy uses constant assumed draw throughout scheduled production; not measured energy consumption",
            "Demand-capped calculation charges full simulated shift cost but values no output beyond demand; production is not rescheduled",
            "Low/base/high cost cases reuse identical simulated output; they are not confidence intervals",
            "Capital is allocated straight-line; no discounted cash-flow analysis or unsupported payback claim",
            "Timing and quality sensitivity from earlier experiments remains necessary before a real investment decision",
        ],
    }
    (folder / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    with (folder / "runs.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(runs[0]))
        writer.writeheader()
        writer.writerows(runs)
    (ROOT / "configs/economics/scenarios.json").write_text(
        json.dumps(cases, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
