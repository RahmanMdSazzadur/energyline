# EnergyLine 1.1.0 — combined prototype release

Released 10 November 2026. This is the first single package containing the reviewed software study and the later electrical and Arduino demonstrations. The earlier software-only v1.0.1 archive remains a historical release; its content has not been re-labeled as a hardware build.

## Included components

| Component | Location | Status |
|---|---|---|
| Five-station production-flow and cost study | `src/`, `configs/`, `results/` | Assumption-based model; analytical/reference and software tests |
| Virtual S3 cell and controller-to-line adapter | `src/controls/`, `src/equipment_model/`, `src/cell/` | Software fault/recovery and commissioning evidence |
| n8n workflow definitions | `n8n/` | Manual experiment and commissioning orchestration; no credentials or live instance data |
| Mechanical product, fixture and line layout | `cad/` | Concept sources and drawings; not mechanically qualified |
| S3 5 V LED bench PCB, Revision A | `electrical/s3_interface/` | Routed two-layer design; native files, assembly BOM, 3D view and configured KiCad checks |
| Generic-device circuit simulation | `electrical/s3_interface/simulation/` | SPICE deck, engine log, CSV waveforms, report and 12 checks |
| Arduino Uno controller demonstration | `wokwi/` | Standalone firmware/wiring, source tests, public project URL and live test evidence |
| Documentation and video | `docs/`, `media/` | Case study, assumptions, validation limits and existing two-minute software demonstration |

## Component boundaries

The Wokwi sketch implements a three-second LED cycle with part/cover/permit faults and reset logic. It does not implement the Python S3 controller's feedback, unit IDs, journals, retained-part recovery, process results or transfer sequence. Its output-off fault behavior applies to an LED, not to release or retention of a physical workpiece. It has no n8n or Python connection.

The KiCad circuit is a 5 V LED interface, not a solenoid or motor driver. Its transistor and LED simulation models are generic, the fuse does not trip in SPICE, and EMC/ESD, tolerances, thermal behavior and hardware power-loss recovery remain untested. The local fuse 3D envelope is included and labeled in `electrical/s3_interface/models/README.md`.

The PCB is an engineering prototype prepared for fabrication review, not a certified industrial product. Before ordering, verify actual components, connector compatibility and mechanical fit. Before claiming function, build and measure a prototype using the assembly instructions.

## Release cleanup

The unified README, offline index, case study, validation statement and portfolio page now describe all three technical parts. The local download route points to the combined archive. Every packaged file has a SHA-256 entry in `RELEASE_MANIFEST.json`; the archive checksum is supplied separately.

Runtime containers, credentials, n8n databases, live experiment storage, caches, editor locks, recovery history, scratch work, obsolete PCB placement drafts and nested old release archives are excluded. CSV circuit samples are included; duplicate raw SPICE text samples are omitted. Current PCB manufacturing layers and plated/non-plated drill files are included directly.

The package is ready to share as a documented simulation and prototype-design project. Physical validation is a later phase.

## Public access

The repository includes an MIT license for original work, third-party notices, contribution instructions, a static GitHub Pages overview and a read-only GitHub Actions check workflow. Versioned release assets contain the complete reviewed package. The static site does not host the Python API or n8n.
