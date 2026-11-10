# EnergyLine: assembly line simulation

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
| Manual line | 3 + 1 | 155.8 | 0/200 | EUR 5.46 |
| Improved S3 fixture | 3 + 1 | 173.0 | 0/200 | EUR 4.96 |
| Two manual S3 fixtures | 4 + 1 | 200.5 | 0/200 | EUR 5.32 |
| Faster S3 | 3 + 1 | 195.5 | 0/200 | EUR 4.51 |
| Faster S2/S3 · 3 operators | 3 + 1 | 251.9 | 183/200 | EUR 3.66 |
| Faster S2/S3 · 4 operators | 4 + 1 | 260.9 | 198/200 | EUR 4.31 |

The manual and fixture cases are fully attended and have no modeled equipment breakdowns. Proposed automated operations use assumed 50% attendance and synthetic failure/repair inputs. That difference matters: the table compares design hypotheses, not measured manual and automated equipment.

The lower-cost alternative uses two actual S3 resource slots in the flow model. In a matched comparison with four production operators and one rework operator, the second S3 resource raises average output from 163.4 to 200.5. Neither case reaches 240 in any of its 200 shifts. S2 becomes the stronger constraint.

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

Accelerated cell seconds are scaled to an assumed 70-second nominal line cycle. The cell resets per cycle, and line attendance remains a separate assumption. Across 200 integrated shifts, average accepted output is 270.5; 200/200 meet 240, with a 95% interval of 98.1% to 100.0%. This adapter uses a different fault model from the economic study, so I report the two results separately.

## Verification and use

The repository has 103 passing tests. Numerical studies can be regenerated with `python3 scripts/reproduce.py`. Each study records its configuration, seeds and source checksums. The browser application exposes the experiment studio, cell trace playback and cost comparison.

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

## Electrical prototype and Arduino demonstration

The combined release also includes an 80 × 70 mm, two-layer PCB for a 5 V LED bench interface. KiCad reports zero configured DRC violations, unconnected items and schematic parity findings, and zero reported ERC violations. Twelve ngspice checks pass using generic semiconductor models. The fuse visualization is an original simplified envelope based on manufacturer dimensions; it is not manufacturer CAD.

The Wokwi Arduino Uno demonstration runs a three-second LED cycle and latches faults for permit, cover or part loss. Its controller core passes 26 native C++ assertions; six live simulator cases are recorded. It is standalone and does not implement the full virtual controller's clamp feedback, retained-part recovery, unit journal, process-result or transfer functions. No n8n connection or physical actuator is included.

These are complementary deliverables, not one end-to-end physical machine. Read electrical/s3_interface/ASSEMBLY.md and wokwi/README.md for their wiring and validation boundaries. The existing two-minute video covers the software study and does not demonstrate a physical build.
