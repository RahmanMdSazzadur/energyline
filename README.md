# EnergyLine

Assembly-line simulation, a virtual fastening cell, n8n workflows, a routed PCB prototype and a standalone Arduino demonstration.

Start with `START_HERE.md` or open `RELEASE_INDEX.html` from the extracted folder. Version 1.1.1 combines all current deliverables in `EnergyLine-v1.1.1-final.zip`.

EnergyLine studies how a five-station mock energy-module assembly line could meet a demand of 240 good units per shift. The model compares staffing, finite buffers, a second manual fixture and selective automation. Process times, failure rates, quality inputs and prices are assumptions. No physical production data is used.

## Access and reuse

- Public repository: https://github.com/RahmanMdSazzadur/energyline
- Online project overview: https://rahmanmdsazzadur.github.io/energyline/
- Download the reviewed package: https://github.com/RahmanMdSazzadur/energyline/releases/tag/v1.1.1
- Interactive Arduino demonstration: https://wokwi.com/projects/480261288480719873

The project page serves static documentation, video, drawings and saved circuit results. It does not run the Python app or n8n in the browser. To run the full app, clone this repository, enter its folder, and follow the local setup below. GitHub Actions checks the software tests, Arduino controller core and archive contents; it does not run physical hardware tests.

```sh
git clone https://github.com/RahmanMdSazzadur/energyline.git
cd energyline
python3 src/api/server.py
```

Free Python hosting configuration is provided in `render.yaml`; see `docs/hosting.md`. Deployment requires a Render account and the Free compute plan. No live Python URL is claimed until deployment is verified.

Original project work is available under the MIT license. See `LICENSE`, `THIRD_PARTY_NOTICES.md` and `CONTRIBUTING.md`.

## Main result

With the faster S2/S3 configuration, four production operators plus one rework operator meet demand in 198 of 200 simulated shifts. The 95% Wilson lower bound is 96.4%. Three production operators cost less per unit but meet demand in 183 of 200 shifts, with an 86.8% lower bound.

Adding a second manual S3 resource at fixed staffing raises output from 163.4 to 200.5 units per shift. S2 then limits the line. The study therefore supports investigating both S2 and S3 rather than buying an S3 machine on the basis of its standalone cycle time.

These results apply to the configured model. Loading, walking, unloading and inspection performance need measured inputs before an equipment decision.

## Run locally

Use Python 3.13.7. The application and tests use the standard library; no pip packages are required.

`python3 src/api/server.py`

Open `http://localhost:8787/portfolio` for the case study, drawings and video. The application also provides the experiment studio at `/`, the S3 cell at `/cell` and the cost comparison at `/costs`. These are local addresses, not public hosting links.

For Docker and n8n setup, see `n8n/README.md`. n8n coordinates experiments and commissioning tests; it does not control physical motion.

## Verify and reproduce

- Tests: `python3 -m unittest discover -s tests -q`
- Regenerate numerical evidence and drawings: `python3 scripts/reproduce.py`
- Optional video rendering: `python3 scripts/build_demo.py` (requires `requirements-media.txt` and ffmpeg).
- Build the source archive: `python3 scripts/package_release.py`

The reviewed version has 103 passing tests and 11 recorded commissioning cases. Six cost configurations each use 200 replications. Separate studies cover staffing, timing variation, failures, quality, parallel S3 resources and the per-unit controller adapter. Seeds, configurations and checksums are saved with the results.

## Project structure

- `src/simulation/`: production flow, operators, buffers, quality and reliability.
- `src/controls/`, `src/equipment_model/`, `src/cell/`: S3 controller, plant and commissioning harness.
- `src/analysis/`: experiment drivers and conversion-cost calculations.
- `configs/`: model and cost inputs.
- `tests/`: reference cases, invariants, fault responses and API checks.
- `cad/`: OpenSCAD concepts, dimensioned SVG drawings and a DXF layout.
- `docs/final_case_study.md`: methods, results and engineering interpretation.
- `docs/engineering_review.md`: review findings and corrections.
- `docs/assumptions_register.md`, `docs/requirements_audit.csv`: input and evidence records.
- `n8n/`: workflow definitions and setup instructions.
- `media/`: two-minute software demonstration and captions.
- `electrical/`: KiCad project, routed Revision A PCB, 3D envelope, ngspice evidence and fabrication files.
- `wokwi/`: Arduino sketch, virtual wiring, tests and saved project URL.
- `docs/release_notes.md`: combined release contents and component boundaries.

## Limits

The cell and line adapter run in software. Cell timings are scaled to an assumed line cycle, and the adapter resets the cell each cycle. Its results are reported separately from the economic study.

Mechanical CAD is conceptual and has not been compiled or qualified for manufacture. The electrical PCB has passed configured KiCad DRC, ERC and schematic parity checks, but has not been manufactured or physically tested. The Wokwi LED controller is a standalone demonstration, not a full port of the virtual S3 controller or a connection to n8n. No measured assembly times, real machine operation, supplier quotations or certified safety functions are claimed. The model omits separate walking/unloading tasks, inspection errors, constrained repair labor, replenishment and shift carryover. Good-unit materials and general overhead are excluded from the reported conversion cost.

Version 1.1.1 is a combined simulation and engineering-prototype release. PCB Revision A and the Wokwi demonstration retain their own validation limits; see `docs/scope_and_validation.md`.
