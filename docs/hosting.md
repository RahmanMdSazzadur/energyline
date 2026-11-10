# Hosting the full Python demo on Render Free

The GitHub Pages site is static. A Render web service runs the actual Python API, experiment studio, virtual S3 cell, costs and portfolio without requiring visitors to install Python. The repository includes `render.yaml` with an explicitly Free plan; no paid database, disk or other resource is defined.

## Verified public service

Live app: https://energyline-demo.onrender.com/

The service is Python 3.13.7 on the Free compute plan in Frankfurt. Twelve public HTTPS smoke checks passed, covering health, five pages, a real line experiment, CSV export, an S3 demo/trace, costs, video byte ranges and the release redirect. A browser-run two-shift manual experiment also completed and displayed its results. These checks establish basic deployment function, not production load capacity.

## Deploy

1. Sign in to Render. Use its free workspace and do not add a payment method for this no-spend demo.
2. Create a Blueprint from `https://github.com/RahmanMdSazzadur/energyline`, branch `main`, using `render.yaml`. Alternatively create a Python Web Service from the public Git repository and apply the settings below.
3. Confirm the compute plan says **Free** before creating the service. If Render requires payment or a paid resource, stop rather than upgrading.
4. Python: `3.13.7`. Build: `python3 -m compileall -q src`. Start: `python3 src/api/server.py --host 0.0.0.0 --port $PORT`. Health check: `/api/health`.
5. Set the environment variables from `render.yaml`. The public-demo setting shows a shared/temporary-data notice and permits one compute request at a time. Other requests receive a retry message rather than queueing unlimited simulation jobs.
6. Once Render assigns a URL and the service is live, verify `/api/health`, `/`, `/cell`, `/costs`, `/portfolio` and `/circuit-simulation`. Run a small line experiment and a normal S3 demo, then check JSON/CSV downloads and video playback.
7. Add that verified URL to the repository homepage and project page. Do not advertise an assumed service URL before deployment has succeeded.

## Free-plan behavior

Render's free web services sleep after 15 minutes without inbound traffic. Waking can take around one minute. Local data is ephemeral and can disappear on sleep, restart or redeploy. All visitors share the public demo's synthetic experiment list; this is not private user storage. Download any results you want to retain. Do not enter confidential information in a public deployment.

The free workspace has monthly instance-hour, bandwidth and build-minute limits. Without a payment method, excess use is handled by service/build suspension rather than buying additional capacity. This is a portfolio demonstration, not an always-on production service. Do not configure keep-alive traffic to defeat free-tier sleeping.

The generated SQLite database and run files live under `/tmp/energyline-demo-runs`. The repository's saved comparison studies and commissioning evidence remain read-only baseline artifacts. No n8n instance, real hardware or private credentials are hosted. The release-download endpoint redirects to the canonical GitHub release ZIP, because generated release files are not stored in Git.

## Environment variables

| Variable | Purpose |
|---|---|
| `PORT` | Hosting platform's assigned listening port |
| `PYTHON_VERSION` | Pins the Render Python runtime |
| `ENERGYLINE_PUBLIC_DEMO=1` | Shared-data notice and single compute-job gate |
| `ENERGYLINE_DATA_DIR` | Directory for runtime SQLite, result JSON and event CSVs |
| `ENERGYLINE_RELEASE_URL` | Canonical public GitHub release asset URL |

Local behavior stays unchanged when public-demo variables are absent. Full reproduction and software tests run separately in GitHub Actions; the Render build does not recompute every study or install desktop CAD tools.

Provider references checked 10 November 2026:
- https://render.com/docs/free
- https://render.com/docs/python-version
- https://render.com/docs/blueprint-spec


## Public usage protection

When `ENERGYLINE_PUBLIC_DEMO=1`, all three compute endpoints share these
single-instance limits:

- One active job, with no waiting job queue.
- At most 10 job starts in a rolling minute and 60 in a rolling hour across all
  visitors. No IP addresses or visitor cookies are used for this budget, so
  changing a forwarded-IP header does not bypass it. Counters reset on restart.
- At most 30 simulated shifts per experiment. Larger studies can use the local app.
- Each job runs in a separate Python process. After 30 seconds that process is
  killed and reaped before another compute job is admitted. Partial files from a
  timed-out job are removed.
- HTTP reads have a 10-second socket timeout and the server admits at most 24
  connection-handler threads. Additional connections are closed without starting
  another handler. The existing 4 KiB request-body limit remains in place.
- Cleanup runs at startup and before/after compute jobs. It keeps at most 50
  experiments, 20 commissioning suites and 250 cell traces, removes artifacts
  older than 24 hours when cleanup runs, and trims generated artifact files to
  80 MiB. Database rows are bounded by those counts and vacuumed after eviction;
  the database itself is additional to the artifact-file budget. Expired or
  partially evicted records are removed with their files. This acts only on the
  dedicated runtime data directory, not source files or tagged release archives.

Busy/limited requests return HTTP 429, `Retry-After` and an error message with the
wait time. Overlong jobs return HTTP 504. Ordinary page and evidence reads do not
consume the compute budget. Public mode exposes the configured compute limits in
`/api/health` and the page notice. Local mode retains the original 100-shift limit
and does not use public quotas, subprocess deadlines or automatic deletion.

These are resource bounds for a free demonstration, not a guarantee of immunity
to denial-of-service attacks. A visitor can consume the shared quota; large
traffic floods still depend on Render's edge protection. Multiple app processes
or instances would need a shared/distributed limiter instead of this in-memory
budget. No additional paid service is required.

Render's explanation of edge versus application-level protection:
https://render.com/articles/how-render-handles-ddos-attacks
