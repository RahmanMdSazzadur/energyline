"""Compare synthetic fixed-time staffing cases with the same buffers and policy."""

import copy
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/simulation"))
from finite_buffers import FIELDS, simulate


def main():
    config = json.loads((ROOT / "configs/shared_operators.json").read_text())
    destination = ROOT / "results/staffing"
    destination.mkdir(parents=True, exist_ok=True)
    rows = []
    for count in (1, 2, 3, 5):
        case = copy.deepcopy(config)
        case.update(operator_count=count, scenario=f"manual_shared_{count}_operators")
        events, summary, _ = simulate(case)
        folder = destination / f"operators_{count}"
        folder.mkdir(exist_ok=True)
        (folder / "config.json").write_text(json.dumps(case, indent=2) + "\n")
        (folder / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        with (folder / "events.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(events)
        row = {
            key: summary[key]
            for key in [
                "operator_count",
                "accepted_units",
                "unfinished_units",
                "paid_labor_hours",
                "good_units_per_paid_labor_hour",
                "demand_met",
            ]
        }
        rows.append(row)
        print(row)
    with (destination / "comparison.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
