"""Build the case study and local project pages from recorded results."""

import csv
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = json.loads((ROOT / "release_config.json").read_text())["version"]


def markdown_html(source):
    output, table = [], []
    in_list = False

    def inline(text):
        text = html.escape(text)
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)

    def flush_table():
        nonlocal table
        if not table:
            return
        output.append('<div class="table-wrap"><table>')
        for index, row in enumerate(table):
            if index == 1 and all(re.fullmatch(r"[:\- ]+", cell) for cell in row):
                continue
            tag = "th" if index == 0 else "td"
            output.append(
                "<tr>"
                + "".join(f"<{tag}>{inline(cell)}</{tag}>" for cell in row)
                + "</tr>"
            )
        output.append("</table></div>")
        table = []

    for line in source.splitlines():
        if line.startswith("|"):
            if in_list:
                output.append("</ul>")
                in_list = False
            table.append([cell.strip() for cell in line.strip().strip("|").split("|")])
            continue
        flush_table()
        if line.startswith("- "):
            if not in_list:
                output.append("<ul>")
                in_list = True
            output.append("<li>" + inline(line[2:]) + "</li>")
            continue
        if in_list:
            output.append("</ul>")
            in_list = False
        if not line.strip():
            continue
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            output.append(f"<h{level}>{inline(line[level:].strip())}</h{level}>")
        else:
            output.append("<p>" + inline(line) + "</p>")
    flush_table()
    if in_list:
        output.append("</ul>")
    return "\n".join(output)


def main():
    costs = json.loads((ROOT / "results/economics/comparison.json").read_text())
    linked = json.loads((ROOT / "results/final/integrated_comparison.json").read_text())
    parallel = json.loads((ROOT / "results/final/parallel_comparison.json").read_text())
    verification = json.loads(
        (ROOT / "results/final/reproduction_verification.json").read_text()
    )
    test_log = next(
        item["test_output"]
        for item in verification["commands"]
        if "test_output" in item
    )
    test_count = int(re.search(r"Ran (\d+) tests", test_log).group(1))
    case_rows = "\n".join(
        f"| {case['label']} | {case['production_operators']} + 1 | {case['mean_good_units']:.1f} | "
        f"{case['demand_attainment']['240']['successful_shifts']}/200 | "
        f"EUR {case['cost_sensitivity']['base']['pooled_conversion_cost_per_good_unit_eur']:.2f} |"
        for case in costs["cases"]
    )
    readme = f"""# EnergyLine

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

The reviewed version has {test_count} passing tests and 11 recorded commissioning cases. Six cost configurations each use 200 replications. Separate studies cover staffing, timing variation, failures, quality, parallel S3 resources and the per-unit controller adapter. Seeds, configurations and checksums are saved with the results.

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

Version {VERSION} is a combined simulation and engineering-prototype release. PCB Revision A and the Wokwi demonstration retain their own validation limits; see `docs/scope_and_validation.md`.
"""
    case_study = f"""# EnergyLine: assembly line simulation

## Problem

The design target is 240 accepted mock energy modules per shift. Seven production hours within an eight-hour paid shift give a demand takt of 105 seconds. The question is which combination of staffing, fixtures and automation can meet that target consistently.

I used an inert product concept with one tray, four inserts, a removable cover, four fastening positions and a serial number. The five operations are tray identification/loading, insert loading, cover fitting/fastening, inspection/test and labeling/release. All process and cost inputs are assumed; I haven't collected manual timing measurements or operated production equipment for this study.

## Baseline and model

The starting mean operation times are 45, 120, 150, 90 and 60 seconds. S3 is the first constraint, while S2 also exceeds takt. A deterministic single unit takes 465 seconds to cross an empty line. With dedicated resources and no losses, the shift model produces 165 units. I used these reference cases to check timing before adding variability.

The discrete-event model includes finite FIFO buffers, blocking after service and shared operators. An operator is reserved for attended work and released for the unattended part of a machine cycle. Failure clocks run during processing; interrupted work resumes after repair. Inspection at S4 detects all modeled defects. A failed unit receives at most one offline rework attempt, which consumes a separate paid operator. Recovered units return before S5 and only count as good output after labeling and release.

The shift starts empty. Work left at the boundary remains unfinished; overtime is excluded. Every run checks released units = accepted + scrapped + unfinished. Tests also check exclusive operator assignments, buffer capacities, duplicate completion, time accounting and seed reproducibility.

## Configuration comparison

Each configuration below uses 200 replications with common processing streams for comparison. Repetitions within a configuration use different seeds. All cases include one rework operator in addition to the stated production staffing.

| Configuration | Production + rework staff | Mean good units/shift | Shifts meeting 240 | Base conversion cost/good unit |
| --- | --- | ---: | ---: | ---: |
{case_rows}

The manual and fixture cases are fully attended and have no modeled equipment breakdowns. Proposed automated operations use assumed 50% attendance and synthetic failure/repair inputs. That difference matters: the table compares design hypotheses, not measured manual and automated equipment.

The lower-cost alternative uses two actual S3 resource slots in the flow model. In a matched comparison with four production operators and one rework operator, the second S3 resource raises average output from {parallel[0]['mean_good_units']:.1f} to {parallel[1]['mean_good_units']:.1f}. Neither case reaches 240 in any of its 200 shifts. S2 becomes the stronger constraint.

For the faster S2/S3 option, three production operators meet demand in 183/200 shifts. The observed rate is 91.5%, but the 95% Wilson lower bound is only 86.8%. Four production operators reach 198/200, with a 96.4% lower bound. I would carry the four-operator option forward for validation at the 240-unit target. The cheaper three-operator case needs better evidence of its reliability or a change to the process/allocation policy.

At a demand of 160, the fixture improvement is worth testing first. None of the evaluated configurations establishes the attainment criterion at 320.

## Cost interpretation

The base cost model includes paid labor, energy, consumables, maintenance, deployment allocation and incremental scrap material loss. Deployment includes equipment, fixtures, controls, integration, commissioning, training, installation and contingency. Capital is allocated over five years, 250 operating days/year and two shifts/day.

All prices are planning assumptions. Good-unit materials, premises, overhead, taxes and finance are excluded, so this is conversion cost rather than total product cost. The four-production-operator S2/S3 case costs EUR 4.31 per completed good unit under base assumptions. Charging the full shift while giving no value to output above demand raises that figure to EUR 4.69 per demand-capped unit.

I haven't calculated payback. There is no established contribution margin, sold incremental output or verified staffing reduction. Reassigning an operator is not treated as a cash saving.

## S3 fixture and control sequence

The fixture concept uses three support pads, two long-edge contacts and one short-edge stop. Contact pads are replaceable. Product and fixture geometry are supplied as editable OpenSCAD sources, with dimensioned SVGs and a DXF line layout.

The reviewed hole-fit calculation allows 0.5 mm position error on each axis. The radial worst case is sqrt(0.5² + 0.5²) = 0.707 mm. A 5.0 ±0.15 mm cover hole around an assumed 3.0 mm fastener gives 0.925 mm minimum radial clearance and a 0.218 mm assumed margin. The original 4.5 mm hole was insufficient for this two-axis error budget and has been corrected. This remains a design calculation, not a metrology result.

The controller and equipment model exchange I/O signals only. The normal sequence is IDLE, CLAMPING, PROCESSING, CHECK_RESULT, WAIT_TRANSFER, RELEASE and COMPLETE. A completed result stays latched while downstream is unavailable. Failed results route to rework.

Faults inhibit motion and process outputs. Reset acknowledges a resolved cause into a nonmoving recovery state; a separate recovery request opens the fixture and quarantines uncertain work. The review added checks for part/cover loss, changed unit identity, stale process results, contradictory or lost clamp feedback, permit loss during recovery and restart with an unresolved journal entry.

Eleven scripted commissioning cases cover normal operation and the specified abnormal sequences. Direct unit tests cover the added interlocks. This is software testing, not a certified machinery safety function or hardware power-loss test.

## Controller-to-line adapter

The adapter executes an S3 controller/equipment cycle using the flow unit's ID. Cycle duration and pass/fail/quarantine disposition affect the line. Failed process results become S3-origin defects; uncertain faulted cycles are conservatively scrapped. Separate examples preserve the matching line event and cell trace.

Accelerated cell seconds are scaled to an assumed 70-second nominal line cycle. The cell resets per cycle, and line attendance remains a separate assumption. Across {linked['replications']} integrated shifts, average accepted output is {linked['mean_good_units']:.1f}; {linked['target_240_successes']}/{linked['replications']} meet 240, with a 95% interval of {linked['wilson_95_lower']:.1%} to {linked['wilson_95_upper']:.1%}. This adapter uses a different fault model from the economic study, so I report the two results separately.

## Verification and use

The repository has {test_count} passing tests. Numerical studies can be regenerated with `python3 scripts/reproduce.py`. Each study records its configuration, seeds and source checksums. The browser application exposes the experiment studio, cell trace playback and cost comparison.

Two n8n workflows run line experiments and the commissioning suite. A separate expected-failure test checks the commissioning error branch. The workflows are manual and inactive; n8n coordinates tests and records rather than machine motion.

## Validation still needed

This is a simulation study with concept tooling. Before using its results for equipment selection, I would collect manual timings across sessions, measure loading/unloading and walking, test inspection performance, constrain maintenance/material handling and obtain equipment/integration quotes. The fixture needs CAD compilation, manufacturing review, force/deflection checks and dimensional inspection.

Those inputs could change the preferred configuration. Test coverage and confidence intervals describe software behavior and sampling uncertainty within the model; they do not establish the accuracy of the assumed factory inputs.

## Evidence

- `results/economics/comparison.json`: six cost configurations and their input assumptions.
- `results/final/parallel_comparison.json`: matched one/two-resource manual S3 study.
- `results/final/integrated_comparison.json`: controller adapter experiment.
- `results/final/linked_cell_examples.json`: corresponding unit IDs and cell traces.
- `results/s3_commissioning/commissioning.csv`: recorded commissioning outcomes.
- `cad/dimensions.json`: reviewed geometry and tolerance budget.
- `docs/requirements_audit.csv`: requirements and evidence status.
- `docs/engineering_review.md`: findings, corrections and remaining limits.
"""
    (ROOT / "README.md").write_text(readme)
    case_study += """
## Electrical prototype and Arduino demonstration

The combined release also includes an 80 × 70 mm, two-layer PCB for a 5 V LED bench interface. KiCad reports zero configured DRC violations, unconnected items and schematic parity findings, and zero reported ERC violations. Twelve ngspice checks pass using generic semiconductor models. The fuse visualization is an original simplified envelope based on manufacturer dimensions; it is not manufacturer CAD.

The Wokwi Arduino Uno demonstration runs a three-second LED cycle and latches faults for permit, cover or part loss. Its controller core passes 26 native C++ assertions; six live simulator cases are recorded. It is standalone and does not implement the full virtual controller's clamp feedback, retained-part recovery, unit journal, process-result or transfer functions. No n8n connection or physical actuator is included.

These are complementary deliverables, not one end-to-end physical machine. Read electrical/s3_interface/ASSEMBLY.md and wokwi/README.md for their wiring and validation boundaries. The existing two-minute video covers the software study and does not demonstrate a physical build.
"""
    (ROOT / "docs/final_case_study.md").write_text(case_study)
    scope = """# Validation status

EnergyLine is a software simulation and concept-tooling study. Process, reliability, quality, attendance and cost inputs are assumed. No manual timing measurements, physical equipment qualification or supplier quotations are supplied.

Software verification covers analytical references, invariants, controller fault responses and repeated simulated shifts. The requirement audit distinguishes these checks from missing empirical validation. Confidence intervals quantify sampling uncertainty within the model.

The concept drawings need CAD compilation, manufacturing review and metrology. The cell adapter resets each cycle and applies an assumed time scale. Walking, separate unloading, inspection errors, constrained maintenance, replenishment and shift carryover are omitted.

The electrical extension includes a routed PCB with manufacturing exports. Saved KiCad checks report zero configured DRC violations, unconnected items, schematic mismatches and ERC findings; the generic-model ngspice run passes 12 checks. No physical board has been built, and no EMC/ESD, environmental, thermal, fuse-selectivity or certified safety validation is supplied. The fuse uses a simplified local 3D envelope, and purchased-part/enclosure fit remain unverified.

The Wokwi Arduino sketch is a standalone LED bench demonstration with 26 controller assertions and recorded live simulator checks. It is not connected to the Python virtual cell or n8n and does not implement their full production logic. A simulation reset does not demonstrate hardware power-loss recovery.

The combined release packages the software, electrical prototype and Wokwi source together. The project can be presented as an engineering simulation and prototype-design study. It does not establish factory readiness, certified safety or measured production improvement.
"""
    (ROOT / "docs/scope_and_validation.md").write_text(scope)
    # Keep evidence status explicit without repeating the development history.
    audit = ROOT / "docs/requirements_audit.csv"
    if audit.exists():
        with audit.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
            fields = list(rows[0])
        for row in rows:
            if row["id"] == "G6":
                row["requirement"] = (
                    "Consistent documentation, demonstration and source archive"
                )
                row["status"] = "PASS: DOCUMENTATION"
            if row["id"] == "G2":
                row["status"] = "SOFTWARE VERIFIED; MEASUREMENT ABSENT"
            if row["id"] == "G4":
                row["status"] = "CONCEPT AND SOFTWARE EVIDENCE; HARDWARE UNVALIDATED"
        with audit.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    style = """<style>article{max-width:940px;margin:auto}article h1{font-size:40px}article h2{font-size:23px;margin:35px 0 15px}article p,article li{font-size:14px;line-height:1.85;color:#52674e}article code{font-size:12px;background:#e9eee1;padding:2px 4px;overflow-wrap:anywhere}table{border-collapse:collapse;font-size:12px;width:100%}td,th{padding:12px;border:1px solid #d5dfcc;text-align:left}.table-wrap{overflow:auto}.panel{background:white;border:1px solid #dbe3d3;border-radius:10px;padding:24px;margin:22px 0}.panel p{font-size:14px;line-height:1.8;color:#52674e}.actions{display:flex;gap:14px;flex-wrap:wrap;margin:24px 0}.actions a{color:#244f3d;font-size:13px}video{width:100%;background:#e7ecde;border-radius:8px}.designs{display:grid;grid-template-columns:1fr 1fr;gap:16px}.designs img{width:100%}.designs a:last-child{grid-column:1/-1}@media(max-width:760px){.designs{display:block}}</style>"""

    def page(title, body):
        return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><link rel="stylesheet" href="/style.css">{style}</head><body><header><a class="brand" href="/portfolio">EnergyLine</a><a class="pill" href="/">Experiment studio</a></header><main>{body}</main></body></html>'

    (ROOT / "web/case_study.html").write_text(
        page(
            "EnergyLine | Case study",
            "<article>" + markdown_html(case_study) + "</article>",
        )
    )
    review = ROOT / "docs/engineering_review.md"
    if review.exists():
        (ROOT / "web/engineering_review.html").write_text(
            page(
                "EnergyLine | Technical review",
                "<article>" + markdown_html(review.read_text()) + "</article>",
            )
        )
    body = f"""<section class="intro"><p class="eyebrow">ASSEMBLY SIMULATION | V{VERSION}</p><h1>EnergyLine</h1><p>Five-station production flow, a virtual fastening cell and configuration cost comparisons.</p></section><div class="actions"><a href="/case-study">Case study</a><a href="/review">Technical review</a><a href="/downloads/release.zip">Download source and evidence</a><a href="/cell">S3 cell</a><a href="/costs">Cost comparison</a></div><section class="panel"><h2>What the model shows</h2><p>Improving S3 alone moves the constraint to S2. A second manual S3 fixture increases output, but misses the 240-unit target. The faster S2/S3 case with four production operators and one rework operator reaches demand in 198 of 200 simulated shifts.</p><p>Inputs are assumed. The study includes {test_count} software tests, 11 commissioning cases and 1,200 shifts in the six-configuration cost comparison. Measurement and hardware validation remain necessary before an equipment decision.</p></section><section class="panel"><h2>Two-minute demonstration</h2><p>Model results and recorded controller/equipment traces. Silent, with on-screen captions.</p><video controls preload="metadata" aria-label="EnergyLine two-minute software demonstration"><source src="/media/demo.mp4" type="video/mp4"></video><div class="actions"><a href="/media/demo.mp4">Download video</a><a href="/media/demo.srt">Captions</a></div></section><section class="panel"><h2>Product, fixture and layout</h2><p>Editable CAD concepts and dimensioned drawings. The reviewed tolerance calculation uses a two-axis error budget. These designs have not been qualified for manufacture.</p><div class="designs"><a href="/design/module.svg"><img src="/design/module.svg" alt="Mock module dimensions and radial tolerance calculation"></a><a href="/design/fixture.svg"><img src="/design/fixture.svg" alt="S3 locating fixture concept"></a><a href="/design/layout.svg"><img src="/design/layout.svg" alt="Assembly layout with stations, buffers and rework"></a></div></section><section class="panel"><h2>Reproduce the study</h2><p>The application and tests use Python's standard library. The source archive includes configurations, experiment drivers, assumptions and the review findings. See the README for local setup and the case study for model limits.</p><div class="actions"><a href="/api/portfolio">Project status</a><a href="/api/final-evidence">Integrated experiment</a><a href="/downloads/case-study.md">Case study Markdown</a></div></section>"""
    body = body.replace("<section class=\"panel\"><h2>Reproduce the study</h2>", "<section class=\"panel\"><h2>PCB and Arduino demonstration</h2><p>The combined release includes the routed 5 V LED interface PCB, manufacturing files, assembly instructions and a standalone Wokwi controller demo. Physical hardware remains unbuilt and untested.</p><div class=\"actions\"><a href=\"/circuit-simulation\">Circuit results</a><a href=\"https://wokwi.com/projects/480261288480719873\">Wokwi project</a><a href=\"/downloads/release.zip\">Complete release</a></div></section><section class=\"panel\"><h2>Reproduce the study</h2>")
    (ROOT / "web/portfolio.html").write_text(
        page("EnergyLine | Assembly simulation", body)
    )
    status = {
        "release": VERSION,
        "scope": "Assembly simulation, PCB engineering prototype and standalone Wokwi demonstration",
        "pcb_revision": "A",
        "wokwi_controller_assertions": 26,
        "circuit_checks_passed": 12,
        "tests_passed": test_count,
        "commissioning_cases_passed": 11,
        "economic_configurations": len(costs["cases"]),
        "economic_shift_replications": costs["total_simulated_shifts"],
        "integrated_shifts": linked["replications"],
        "integrated_target_successes": linked["target_240_successes"],
        "process_inputs_measured": False,
        "hardware_validated": False,
        "links": {
            "case_study": "/case-study",
            "video": "/media/demo.mp4",
            "release": "/downloads/release.zip",
        },
    }
    (ROOT / "results/final/release_status.json").write_text(
        json.dumps(status, indent=2) + "\n"
    )
    print("Updated README, case study, validation status and project pages.")


if __name__ == "__main__":
    main()
