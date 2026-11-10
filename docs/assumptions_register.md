# Assumptions register

All values are synthetic unless explicitly identified as verified software behavior.

| ID | Input/boundary | Source/evidence | Revision trigger |
| --- | --- | --- | --- |
| A01 | 240 demand; sensitivities 160/320 | Original educational brief/configs | Actual demand and shift schedule |
| A02 | Seven contiguous production hours; eight paid hours | Configuration | Real break timing/carryover |
| A03 | Manual means 45/120/150/90/60 s | Original assumptions; no measured study | Repeated timed assembly across sessions |
| A04 | Faster S2/S3 65/70 s; fixture S3 110 s | Unvalidated scenario estimates | Fixture/motion study or vendor sequence |
| A05 | Triangular variation ±20%, sensitivity ±40% | Synthetic process-time model | Empirical distributions and session effects |
| A06 | 50% initial attendance at proposed automation | Synthetic labor decomposition | Loading, travel, unloading observations |
| A07 | Processing-time failure clocks; exponential repairs | Synthetic reliability sensitivity | Equipment data and maintenance constraints |
| A08 | Perfect S4 inspection; one fixed-time rework attempt | Synthetic quality/rework model | Detection trials and rework measurements |
| A09 | Two-place buffers; unlimited materials and rework input | Model boundary | Layout/material supply limits |
| A10 | Hypothetical EUR deployment and operating costs | configs/economics/assumptions.json | Quotes, actual rates, maintenance contracts |
| A11 | Mock geometry and tolerance stack | cad/dimensions.json | CAD compilation, manufacture, metrology |
| A12 | Accelerated S3 time scaled to assumed line time | cell_adapter; linked unit evidence | Actual tooling sequence and cycle measurements |
| A13 | Internal software verification only | Unit/commissioning tests | Independent empirical validation |

Source hashes, seeds, Python version and configurations accompany numerical evidence. No measured data is supplied or inferred from the target companies.
