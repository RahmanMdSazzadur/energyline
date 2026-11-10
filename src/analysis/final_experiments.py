"""Final parallel-resource and controller/line integration evidence."""

import copy, csv, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src/simulation"), str(ROOT / "src/analysis")]
from parallel_manual import simulate as parallel
from finite_buffers import simulate
from cell_adapter import execute_cycle, normal_duration
from cost_comparison import build_cases
from variability_experiments import wilson_interval


def main():
    folder = ROOT / "results/final"
    folder.mkdir(parents=True, exist_ok=True)
    manual = next(c["config"] for c in build_cases() if c["id"] == "parallel_s3")
    comparisons = []
    for parallel_count in (1, 2):
        config = copy.deepcopy(manual)
        config["parallel_servers"][2] = parallel_count
        outputs = []
        for rep in range(200):
            config.update(
                seed=20262000 + rep,
                run_id=f"parallel_comparison_{parallel_count}_{rep}",
            )
            _, summary, _ = parallel(config)
            outputs.append(summary["accepted_units"])
        comparisons.append(
            {
                "s3_resources": parallel_count,
                "production_operators": 4,
                "rework_operators": 1,
                "mean_good_units": sum(outputs) / len(outputs),
                "minimum": min(outputs),
                "maximum": max(outputs),
                "target_240_successes": sum(x >= 240 for x in outputs),
                "replications": 200,
            }
        )
        print("Parallel comparison:", comparisons[-1])
    (folder / "parallel_comparison.json").write_text(
        json.dumps(comparisons, indent=2) + "\n"
    )
    config = json.loads((ROOT / "configs/integrated_s3.json").read_text())
    rows = []
    examples = {}
    for rep in range(200):
        config.update(seed=20263000 + rep, run_id=f"integrated_s3_{rep+1:03d}")
        events, summary, _ = simulate(config)
        cycles = summary["cell_integration"]["cycles"]
        rows.append(
            {
                "seed": config["seed"],
                "accepted_units": summary["accepted_units"],
                "scrapped_units": summary["scrapped_units"],
                "unfinished_units": summary["unfinished_units"],
                "released_units": summary["released_units"],
                "linked_cycles": len(cycles),
                "quarantined_cell_cycles": sum(
                    c["outcome"] == "quarantined" for c in cycles
                ),
                "failed_cell_results": sum(c["outcome"] == "fail" for c in cycles),
            }
        )
        for cycle in cycles:
            if cycle["outcome"] not in examples:
                station = next(s for s in config["stations"] if s["id"] == "S3")
                normal_nominal = cycle["time_scale"] * normal_duration()
                replay = execute_cycle(
                    config, station, cycle["unit_id"], normal_nominal
                )
                examples[cycle["outcome"]] = {
                    "flow_run_id": config["run_id"],
                    "seed": config["seed"],
                    "cycle": cycle,
                    "trace": replay["trace"],
                }
        if rep == 0:
            (folder / "integrated_first_shift_summary.json").write_text(
                json.dumps(summary, indent=2) + "\n"
            )
            with (folder / "integrated_first_shift_events.csv").open(
                "w", newline=""
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=list(events[0]))
                writer.writeheader()
                writer.writerows(events)
    successes = sum(r["accepted_units"] >= 240 for r in rows)
    lo, hi = wilson_interval(successes, len(rows))
    report = {
        "config": json.loads((ROOT / "configs/integrated_s3.json").read_text()),
        "replications": len(rows),
        "mean_good_units": sum(r["accepted_units"] for r in rows) / len(rows),
        "target_240_successes": successes,
        "wilson_95_lower": lo,
        "wilson_95_upper": hi,
        "runs": rows,
        "interpretation": "S3 controller and plant executed for each unit; result/duration mapped into flow. 70-second reference is an explicit assumed scaling, not measured cycle time.",
        "quarantine_policy": "Faulted S3 units conservatively counted as scrap, not reworked or passed",
        "limitations": [
            "Per-cycle reset plant/controller, not continuous live industrial control",
            "Line staffing attendance remains an independent assumed fraction",
            "This integration experiment uses a different fault model and is not the economic scenario qualification",
        ],
    }
    (folder / "integrated_comparison.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    (folder / "linked_cell_examples.json").write_text(
        json.dumps(examples, indent=2) + "\n"
    )
    print(
        "Integrated line:",
        report["mean_good_units"],
        "good units,",
        successes,
        "/200 shifts met target",
    )


if __name__ == "__main__":
    main()
