# Software and concept-design risk review

| Failure or misleading claim | Implemented treatment | Verification / residual boundary |
| --- | --- | --- |
| Missing/duplicated units through blocking or rework | Explicit ownership/disposition and mass balance | Flow, quality, parallel and adapter tests |
| One operator assigned simultaneous tasks | Resource reservation and release | Operator trace/time-accounting tests |
| Fault clears and motion resumes without deliberate recovery | Motion/process enables inhibited; reset enters nonmoving recovery | Cell tests; not certified machinery safety |
| Stale/duplicate completion or reused ID | Journal and rising-edge commands; quarantine uncertain units | Commissioning and direct controller tests |
| Rework silently adds good output | Resource/time consumption and S5 rejoin; one attempt | Quality and zero-boundary tests |
| Unlimited queues imply an unrealistically buildable line | Finite main buffers; rework input explicitly unlimited | Documented sensitivity and spatial concept |
| Nominal/assumed timing presented as measured | Synthetic labels, scope audit and separate cell time scale | No empirical baseline/hardware validation claimed |
| Cheap configuration selected despite weak attainment | Wilson lower-bound criterion displayed alongside costs | Conditional model decision, not procurement |
| Geometry interpreted as fabrication/safety approval | Concept markings, tolerance assumptions and validation boundary | CAD compilation, forces, guarding and metrology remain unverified |

No powered physical equipment is operated. A real installation would require a separate engineered risk assessment, suitable hardware protections and commissioning evidence. This software review does not supply them.
