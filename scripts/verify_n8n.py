"""Optional check of existing local EnergyLine workflows via supported n8n CLI.

Does not activate workflows, expose credentials or save raw runtime tokens.
Imports a clearly named inactive expected-failure test utility if absent.
"""

import copy, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def decoded_execution(raw):
    decoder = json.JSONDecoder()
    for i, char in enumerate(raw):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(raw[i:])
        except json.JSONDecodeError:
            continue
        if (
            isinstance(value, dict)
            and value.get("status") == "success"
            and value.get("finished")
        ):
            return value
    raise RuntimeError("No successful execution payload found")


def main():
    output = ROOT / "results/integration"
    output.mkdir(exist_ok=True)
    records = []
    for workflow, node in [
        ("energylineRunExperiment", "Read experiment summary"),
        ("energylineS3Commission", "Commissioning summary"),
    ]:
        process = subprocess.run(
            [
                "docker",
                "exec",
                "-e",
                "N8N_RUNNERS_BROKER_PORT=5691",
                "n8n-n8n-1",
                "n8n",
                "execute",
                f"--id={workflow}",
                "--rawOutput",
            ],
            capture_output=True,
            text=True,
        )
        if process.returncode:
            raise RuntimeError(
                f"{workflow} execution failed; raw logs intentionally not saved"
            )
        execution = decoded_execution(process.stdout)
        summary = execution["data"]["resultData"]["runData"][node][0]["data"]["main"][
            0
        ][0]["json"]
        records.append(
            {"workflow_id": workflow, "status": "success", "summary": summary}
        )
        print(workflow, "PASS", flush=True)
    workflow = json.loads((ROOT / "n8n/workflows/commission_s3.json").read_text())
    workflow["id"] = "energylineFailureBranchCheck"
    workflow["name"] = "EnergyLine — commissioning failure self-test (expected error)"
    node = next(n for n in workflow["nodes"] if n["name"] == "Run all S3 cases")
    node.update(
        type="n8n-nodes-base.set",
        typeVersion=3.4,
        parameters={
            "mode": "raw",
            "jsonOutput": json.dumps(
                {"passed": False, "failed_cases": 1, "report_url": "/test-only-failure"}
            ),
            "options": {},
        },
    )
    folder = ROOT / "n8n/tests"
    folder.mkdir(exist_ok=True)
    path = folder / "failure_path_self_test.json"
    path.write_text(json.dumps(workflow, indent=2) + "\n")
    subprocess.run(
        ["docker", "cp", str(path), "n8n-n8n-1:/tmp/energyline_expected_failure.json"],
        check=True,
        capture_output=True,
    )
    listed = subprocess.run(
        ["docker", "exec", "n8n-n8n-1", "n8n", "list:workflow", "--onlyId"],
        capture_output=True,
        text=True,
        check=True,
    )
    if "energylineFailureBranchCheck" not in listed.stdout.splitlines():
        subprocess.run(
            [
                "docker",
                "exec",
                "n8n-n8n-1",
                "n8n",
                "import:workflow",
                "--input=/tmp/energyline_expected_failure.json",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    process = subprocess.run(
        [
            "docker",
            "exec",
            "-e",
            "N8N_RUNNERS_BROKER_PORT=5691",
            "n8n-n8n-1",
            "n8n",
            "execute",
            "--id=energylineFailureBranchCheck",
            "--rawOutput",
        ],
        capture_output=True,
        text=True,
    )
    correct = (
        process.returncode != 0
        and "S3 commissioning failed: 1 cases" in process.stdout + process.stderr
    )
    records.append(
        {
            "test": "n8n commissioning failure branch",
            "expected_failure_observed": correct,
            "exit_code": process.returncode,
            "method": "Named inactive self-test workflow with mocked failed-suite input; primary workflows unchanged and no workflow activated",
        }
    )
    (output / "final_workflow_verification.json").write_text(
        json.dumps(
            {"n8n_version": "2.46.5", "checks": records, "passed": correct}, indent=2
        )
        + "\n"
    )
    if not correct:
        raise RuntimeError("Expected failure branch was not verified")
    print(
        "Expected failure branch PASS: n8n stopped with intended commissioning error.",
        flush=True,
    )


if __name__ == "__main__":
    main()
