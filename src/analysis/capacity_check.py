"""Nominal capacity arithmetic, not a production simulation."""

import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[2]
    config = json.loads((root / "configs/baseline.json").read_text())
    available = config["shift_duration_s"] - config["planned_nonproduction_s"]
    takt = available / config["target_good_units"]
    print(f"Input source: {config['input_source']}")
    print(f"Scheduled production time: {available:,} seconds")
    print(f"Target: {config['target_good_units']} good units")
    print(f"Demand takt: {takt:.1f} seconds per good unit")
    for station in config["stations"]:
        seconds = station["mean_process_s"]
        print(
            f"{station['id']}: {seconds} s; nominal standalone capacity {available / seconds:.1f} units/shift"
        )
    print(
        "These capacities exclude startup, staffing, downtime, quality and blocking losses."
    )
    print(
        "S2 and S3 exceed demand takt; improving S3 alone may leave S2 as the constraint."
    )


if __name__ == "__main__":
    main()
