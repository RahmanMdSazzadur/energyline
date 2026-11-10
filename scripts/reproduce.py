"""Reproduce EnergyLine software evidence locally. No downloads or n8n changes."""

import argparse, json, platform, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-media",
        action="store_true",
        help="Also regenerate MP4; requires Pillow and ffmpeg",
    )
    args = parser.parse_args()
    steps = [
        ["scripts/build_designs.py"],
        ["-m", "unittest", "discover", "-s", "tests", "-q"],
        ["src/simulation/single_unit.py"],
        ["src/simulation/multi_unit.py"],
        ["src/simulation/finite_buffers.py"],
        ["src/analysis/staffing_comparison.py"],
        ["src/analysis/variability_experiments.py"],
        ["src/analysis/scenario_comparison.py"],
        ["src/analysis/attendance_comparison.py"],
        ["src/analysis/reliability_experiments.py"],
        ["src/analysis/quality_experiments.py"],
        ["src/analysis/cost_comparison.py"],
        ["src/analysis/final_experiments.py"],
        ["src/cell/s3_demo.py"],
    ]
    verification = []
    for command in steps:
        print("Running:", " ".join(command), flush=True)
        process = subprocess.run(
            [sys.executable, *command], cwd=ROOT, capture_output=True, text=True
        )
        record = {"command": ["python3", *command], "exit_code": process.returncode}
        if "-m" in command:
            record["test_output"] = "\n".join(
                line
                for line in (process.stdout + process.stderr).splitlines()
                if "127.0.0.1 - -" not in line
            )
            print(record["test_output"][-300:], flush=True)
        else:
            print(process.stdout[-1300:], flush=True)
        verification.append(record)
        if process.returncode:
            print(process.stderr[-3000:])
            raise SystemExit(process.returncode)
    folder = ROOT / "results/final"
    folder.mkdir(exist_ok=True)
    (folder / "reproduction_verification.json").write_text(
        json.dumps(
            {
                "python_version": platform.python_version(),
                "successful": True,
                "commands": verification,
            },
            indent=2,
        )
        + "\n"
    )
    if args.with_media:
        subprocess.run([sys.executable, "scripts/build_demo.py"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "scripts/build_portfolio.py"], cwd=ROOT, check=True)
    print(
        "Numerical, design and software commissioning evidence reproduced successfully.",
        flush=True,
    )


if __name__ == "__main__":
    main()
