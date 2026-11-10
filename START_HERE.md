# EnergyLine — complete prototype release

Version 1.1.0 · PCB Revision A · 10 November 2026

This package combines the assembly-line study, virtual S3 cell, n8n workflow definitions, mechanical concepts, routed PCB, circuit simulation, Wokwi Arduino demo, documentation and software video. Extract the ZIP before opening files. For a clickable offline contents page, open `RELEASE_INDEX.html`.

## Online access

- Repository and source: https://github.com/RahmanMdSazzadur/energyline
- Static project overview: https://rahmanmdsazzadur.github.io/energyline/
- Versioned download: https://github.com/RahmanMdSazzadur/energyline/releases/tag/v1.1.0
- Arduino simulator: https://wokwi.com/projects/480261288480719873

The static site displays project material and saved results. The Python application and n8n workflows still require local setup. Original work uses the MIT license; third-party notices are retained.

## What to open

| Goal | File or link |
|---|---|
| Understand the project | `README.md` and `docs/final_case_study.md` |
| See the evidence and limits | `docs/scope_and_validation.md` and `docs/release_notes.md` |
| Watch the software demonstration | `media/EnergyLine_demo.mp4` (120 seconds; captions in `media/demo.srt`) |
| Run the local application | `python3 src/api/server.py`, then http://localhost:8787/portfolio |
| Open the current PCB | `electrical/s3_interface/S3_interface.kicad_pro`, then `S3_interface.kicad_pcb` in KiCad |
| Read the wiring and assembly instructions | `electrical/s3_interface/ASSEMBLY.md` |
| Choose parts to match the PCB | `electrical/s3_interface/assembly_bom.csv` |
| Review fabrication layers and drills | `electrical/s3_interface/fabrication/rev_A/` |
| Inspect the board preview | `electrical/s3_interface/exports/S3_rev_A_3d.png` |
| View circuit waveforms | `electrical/s3_interface/simulation/report.html` |
| Run the Arduino demonstration | https://wokwi.com/projects/480261288480719873 |
| Work with the Arduino files locally | `wokwi/sketch.ino`, `wokwi/diagram.json`, `wokwi/README.md` |
| Use n8n orchestration | `n8n/README.md` and `n8n/workflows/` |
| Review mechanical concepts | `cad/README.md`, OpenSCAD sources, dimensioned SVGs and DXF layout |

## Quick verification

Run commands from the extracted `energyline` folder.

1. Use Python 3.13.7 for the application and numerical study. Its core needs no pip dependencies.
2. Run `python3 -m unittest discover -s tests -q` for the software tests.
3. Run `python3 wokwi/test_controller.py` for the Arduino controller core tests. A C++11 compiler named `c++` is required. This does not compile the Arduino GPIO adapter; the complete sketch was compiled and tested in Wokwi.
4. Run `python3 scripts/reproduce.py` to regenerate the software study. This does not rerun KiCad/ngspice or Wokwi. Optional video regeneration uses `--with-media` and requires the media dependencies plus ffmpeg.
5. Follow `electrical/README.md` to reproduce circuit and PCB checks. KiCad 10.0.3 and ngspice 46 were used. Docker may download the specified KiCad image, and ngspice installation requires network access. Standard KiCad library models are external tool dependencies; the local fuse envelope is included.
6. Rebuild the combined archive with `python3 scripts/package_release.py`. This creates `release/EnergyLine-v1.1.0-final.zip`, its manifest and `SHA256SUMS.txt`. The application's `/downloads/release.zip` route requires this generated archive; the ZIP does not contain a nested copy of itself.
7. Verify any extracted release with `python3 scripts/verify_release.py /path/to/EnergyLine-v1.1.0-final.zip`. The script verifies its archive contents and per-file checksums; the separately delivered SHA256 file verifies the whole archive.

The main Docker compose setup expects an existing `n8n_default` network. Running the application directly with Python does not require Docker or n8n. The KiCad browser container is optional and configured separately by `electrical/compose.yaml`. KiCad can also open the native files on a local installation.

## What is verified

- 97 software tests and 11 recorded virtual-cell commissioning cases.
- 12 generic-model ngspice circuit checks.
- Zero reported configured PCB DRC violations, unconnected items, schematic parity issues and ERC violations.
- 26 Arduino controller-core assertions and six recorded live Wokwi scenarios.
- Archive file integrity and a clean-folder software reproduction check; see the separate release verification report supplied with this ZIP.

These counts cover different checks; they are not one end-to-end physical validation suite.

## What this release does not establish

The PCB has not been manufactured, assembled or measured. Component and enclosure fit must be checked against actual purchased parts. The fuse visualization is a simplified envelope, not manufacturer CAD. Mechanical tooling remains conceptual and is not structurally or dimensionally qualified.

The Python virtual cell, Wokwi sketch and electrical bench interface have related signals but are not one connected physical system. Wokwi is a standalone LED demonstration with reduced behavior; n8n coordinates software experiments, not machine motion. No real actuator, certified safety function, EMC/ESD validation or measured production performance is included.

The two-minute video covers the software study, not a physical build or the later PCB/Wokwi extension. Timings, quality, reliability, attendance and prices in the line study remain assumptions. Keep these qualifications when presenting the project.
