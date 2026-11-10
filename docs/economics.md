# Production economics — final software release

Open http://localhost:8787/costs. Select low/base/high hypothetical costs and demand of 160/240/320 good units. Editable inputs: `configs/economics/assumptions.json`. Exact production/deployment cases: `configs/economics/scenarios.json`, generated from `src/analysis/cost_comparison.py`.

Reproduce with `python3 src/analysis/cost_comparison.py`. Six configurations each receive 200 paired independent shifts using seeds 20262000–20262199. The 1,200 production shifts are evaluated under three cost presets, producing 3,600 CSV rows rather than 3,600 independent shifts. All cases use two-place buffers, assumed cycle variation, base defect probabilities and one paid offline rework operator. Proposed automated stations have modeled failures and partial attendance; manual/fixture resources are fully attended and failure-free in this simplified comparison.

## Equations and denominators

Shift cost = paid labor + energy + consumables + maintenance allocation + deployment allocation + incremental scrap material loss.

Deployment is the total configuration cost for equipment, fixtures, controls, integration, commissioning, training and installation, plus assumed contingency. It is not incremental purchase cost. Deployment allocation = total deployment / (useful life × days/year × shifts/day). It is not charged again in the shift cost as an equipment purchase.

Base values: EUR 25/paid hour, EUR 0.20/kWh, five-year life, 250 days/year, two shifts/day, 15% contingency assumed spent, maintenance at 4% of equipment purchase annually. All operators receive eight paid hours. Power draw is assumed constant over seven production hours, including idle. Consumables are EUR 0.25/released unit plus EUR 0.15/rework attempt; scrap adds EUR 4 incremental material loss. Common fixtures include assumed simple rework provision. Maintenance cost is allocated but its labor/resource constraints are not modeled.

Pooled conversion cost = sum of shift costs / sum of accepted units. Zero output produces undefined unit cost, not zero. Good-unit materials, premises, overhead, tax, finance and discounting are excluded. This is not total product cost. Demand-capped cost divides full shift cost by sum(min(good output, demand)); no excess output is assigned value and the production schedule is not changed.

Low/high cases use labor EUR 20/35 per hour, deployment components 0.7/1.4 times base, electricity EUR 0.15/0.30 per kWh. These are cost-sensitivity assumptions, not confidence intervals over prices. Production timing, reliability, quality and staffing sensitivities are reported separately.

## Base results

| Configuration | Production + rework staff | Mean good units | Target 240 attained | Conversion cost/good unit | Total deployment |
| --- | --- | ---: | ---: | ---: | ---: |
| Manual line | 3 + 1 | 155.8 | 0/200 | EUR 5.46 | EUR 2,070 |
| Improved S3 fixture | 3 + 1 | 173.0 | 0/200 | EUR 4.96 | EUR 7,245 |
| Two manual S3 fixtures | 4 + 1 | 200.5 | 0/200 | EUR 5.32 | EUR 4,428 |
| Faster S3 | 3 + 1 | 195.5 | 0/200 | EUR 4.51 | EUR 36,110 |
| Faster S2/S3 · 3 operators | 3 + 1 | 251.9 | 183/200 | EUR 3.66 | EUR 81,880 |
| Faster S2/S3 · 4 operators | 4 + 1 | 260.9 | 198/200 | EUR 4.31 | EUR 81,880 |

A separate matched staffing comparison confirms one manual S3 versus two real S3 resources at four production staff plus one rework staff: mean 163.43 versus 200.505 units, both 0/200 reaching 240. Its evidence is `results/final/parallel_comparison.json`. This closes the parallel-resource alternative without assuming two fixtures halve a single operation's cycle.

## Conditional decision

At 160 demand, validate the low-cost fixture hypothesis first. At 240, faster S2/S3 with four production staff plus rework is the candidate meeting the model's 95% lower attainment bound criterion: 198/200 successes, lower bound 96.4%. Three staff plus rework are cheaper but 183/200 successes give only an 86.8% lower bound. At 320, none of the evaluated cases qualifies. New work would need another constraint/resource change.

The four-production-staff case is EUR 4.31 per completed good unit at base assumptions, but EUR 4.69 per demand-capped unit at demand 240. No payback is calculated: verified annual cash benefit, contribution margin, sold additional output and actual staff reductions are not established. Reassigned labor is not treated as cash savings.

All values are synthetic planning inputs, not quotations, actual spending or measured savings. Fixture/tooling times, geometry, attendance, walking/unloading, maintenance competition, inspection error and actual demand could change the decision. These conditional model candidates are not procurement recommendations.

## Evidence

`results/economics/comparison.json` contains exact inputs, configurations, source hashes, Python version, uncertainty intervals and costs. `runs.csv` contains per-shift results. The final case study and requirements audit state the unvalidated input boundary. The broader integrated cell/line experiment uses a different explicit fault model and is not pooled into this cost comparison.
