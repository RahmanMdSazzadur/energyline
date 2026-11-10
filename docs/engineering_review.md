# Technical review

Scope: production models, cell controls, fixture assumptions, cost interpretation, reproducibility and public documentation. This is a repository review, not independent factory validation.

## Findings and corrections

| Finding | Why it mattered | Correction | Evidence |
| --- | --- | --- | --- |
| The hole-fit check compared a one-axis position budget with radial clearance. | With 0.5 mm possible error on each axis, the radial error can reach 0.707 mm. The original 4.5 mm hole provided only 0.675 mm minimum radial clearance. | Increased the concept cover holes to 5.0 ±0.15 mm. Minimum radial clearance is 0.925 mm, leaving 0.218 mm against the assumed radial error. | `cad/dimensions.json`, dimensioned drawing, `tests/test_design_evidence.py` |
| Permit and communication checks omitted the moving recovery-release state. | A second fault during recovery could leave the controller motion-enable output asserted. | Recovery-release now uses the same permit/communication checks as the normal moving sequence. Returning the permit alone does not resume motion. | `tests/test_controller_review.py` |
| Presence, identity and clamp feedback were only checked at selected transitions. | A removed part, changed ID or lost clamp confirmation could go unnoticed during processing. | Added active-cycle presence/identity/clamp checks, stale-result rejection and a readiness signal requiring an open, empty, permitted fixture. | `tests/test_controller_review.py` |
| Restart checked fixture occupancy but not an unresolved journal with an absent part. | An interrupted unit could remain unreconciled while a new cycle was accepted. | An in-process journal entry now requires recovery even when the fixture is empty. | `tests/test_controller_review.py` |
| Public copy led with completion counts and repeated internal scope history. | It obscured the actual engineering problem and made the report read like a development transcript. | Rewrote the README, case study and project pages around the process, alternatives, findings and validation limits. | README and case study |
| The archive included superseded development documents and local instance evidence. | These added inconsistent milestones, personal environment details and little value for a reader reproducing the model. | Preserve them locally; exclude them and runtime data from the public archive. Use relative reproduction commands. | Packaging script and release manifest |
| Source files contained dense one-line statements. | Fault paths and resource ownership were unnecessarily difficult to inspect. | Applied consistent Python formatting; retained technical comments and regression tests. | `src/`, `tests/`, `scripts/` |

## Assessment

Suitable for presentation as an assembly simulation and virtual-controls project after the recorded checks pass. The strongest evidence is the analytical reference testing, explicit unit/resource accounting, matched parallel-resource comparison and fault/recovery traces.

The project does not yet support an equipment purchase or factory-readiness claim. Process times, attendance, reliability, defect probabilities and prices remain assumptions. The integrated cell uses per-cycle reset and assumed time scaling. Separate walking/unloading, imperfect inspection and constrained maintenance remain outside the model. Concept CAD needs compilation, manufacturing review and dimensional checks.

The reported 95% intervals describe sampling uncertainty for the configured model. They do not validate the input assumptions. Manual cases are modeled without breakdowns while automated cases include failures; this is an explicit design comparison, not a measured automation improvement.

## Publication checks

Use the reviewed archive and its checksum. Keep assumed/simulated labels on results. Describe CAD as conceptual, the cell as virtual and the cost metric as conversion cost. The numerical evidence, video and case study should continue to use the same configuration names and staffing counts, including the dedicated rework operator.

