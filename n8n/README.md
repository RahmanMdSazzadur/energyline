# n8n workflows

n8n coordinates experiments and records results. The Python service runs the simulation and cell tests. It does not depend on n8n for its control sequence.

Tested with n8n 2.46.5. Workflow definitions contain no credentials.

## Setup

Start the application with `docker compose up -d energyline`. The supplied Compose file joins an existing network named `n8n_default`; change that network name if your n8n setup differs. It starts only EnergyLine and publishes the application on host loopback port 8787.

Import the JSON files from `workflows/` into your n8n instance. Check for existing workflow IDs before importing to avoid overwriting a customized copy. Both workflows are manual and inactive. No schedule or external messaging is configured.

The HTTP Request nodes use `http://energyline:8787` inside the Docker network. Open `http://localhost:8787` in the host browser. A remotely hosted n8n instance needs a separately configured reachable service URL; localhost is not a public endpoint.

## Run an experiment

`workflows/run_experiment.json` provides four steps: manual trigger, experiment inputs, simulation request and summary.

Inputs are scenario, production operators, replications, starting seed and target. Available scenario keys: `manual`, `faster_s3`, `faster_s2_s3`, `quality_rework`, `parallel_s3`, `integrated_s3`. The quality, parallel and integrated cases include a dedicated paid rework operator in addition to production staffing.

The workflow uses an execution-based request ID. Retrying the same request reuses the saved experiment. A new execution creates another experiment; the same key with changed inputs or model source returns a conflict.

## Commission the cell

`workflows/commission_s3.json` runs all eleven commissioning cases and returns a persisted report with evidence links. A failed aggregate routes to Stop and Error. The service retains individual failures and continues through the remaining cases.

`tests/failure_path_self_test.json` is an optional inactive utility with an intentionally failed input. Its error is expected and checks the IF/error branch. It is separate from the real commissioning cases.

## API

POST `/api/experiments`: JSON object with `scenario`, `operators` (1–5), `replications` (1–100), `seed`, `target` and optional `request_id`.

POST `/api/cell/demo`: a known `demo` name. POST `/api/cell/commission`: an empty object or optional `request_id`.

GET `/api/scenarios`, `/api/experiments`, `/api/experiments/{id}`, `/api/experiments/{id}/events.csv`, `/api/cell/demos`, `/api/cell/suites/{id}`.

Saved experiments include inputs, seeds, model checksums and results. Unit traces retain ID, station, timing and disposition. Only the first replication event trace is retained by the experiment API. The standalone drivers provide the study evidence used in the case report.

## Local verification

`scripts/verify_n8n.py` checks the primary workflows and the expected-failure utility against the configured local container. It does not activate workflows. This is an optional integration check, separate from numerical reproduction.

Keep n8n credentials, runtime databases and raw execution logs out of public archives. The packaging script includes workflow definitions but excludes local instance records.
