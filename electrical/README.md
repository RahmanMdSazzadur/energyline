# S3 bench interface and simulation

This extension models a 5 V bench interface with an LED mock clamp load and two active-low dry-contact inputs. It is not an industrial actuator circuit or a certified safety circuit.

## Open and reproduce

Start the browser KiCad service with `docker compose -f electrical/compose.yaml up -d`, then open http://localhost:3090. The project inside KiCad is `/project/S3_interface.kicad_pro`.

Export the schematic connectivity before rerunning a changed design:

```sh
docker exec energyline-kicad kicad-cli sch export netlist --format kicadxml --output /project/S3_interface.net.xml /project/S3_interface.kicad_sch
docker exec energyline-kicad apk add --no-cache ngspice
python3 electrical/run_simulation.py
```

The ngspice installation is local to the container and must be repeated if it is recreated. The runner checks the exported net connections, derives component values from that export, and adds explicit simulation sources and generic device models. It runs ngspice externally rather than through KiCad's integrated simulator.

## Results

The 40 ms transient run produced 20,201 samples and passed 12 functional checks. Enabled LED current was 4.149 mA, transistor collector voltage was 0.049 V, and input 10–90% rise time was 219.83 microseconds. Removing the permit inhibited LED current while the command remained high.

Open `s3_interface/simulation/report.html`, or http://localhost:8787/circuit-simulation while the main application is running. Raw results, the SPICE deck, engine log, CSV samples and SVG waveforms are in `s3_interface/simulation/`.

## Model limits

The NPN and LED models are generic; the BC547B is not calibrated against manufacturer measurements. Controller outputs and contacts are ideal sources/switches. The fuse is represented by 1 ohm and does not trip. Input thresholds of 1.5/3.5 V are assumed. Mechanical bounce, EMC, ESD, tolerance and thermal effects are not analyzed. The 100 microsecond RC time constant is not a complete mechanical debounce solution. These results demonstrate modeled behavior, not tested hardware performance.

The combined EnergyLine v1.1.0 release includes this electrical extension alongside the software and Wokwi files.

## Routed PCB Revision A

The current board is `s3_interface/S3_interface.kicad_pcb`, with assembly details in `s3_interface/ASSEMBLY.md`. It uses standard library footprints, four M3 mounting holes and complete two-layer routing. DRC, schematic parity and ERC reports are saved alongside it. Fabrication exports are in `s3_interface/fabrication/rev_A/`. The superseded placement draft is excluded from the combined release.

To regenerate after confirming component choices, copy `electrical/pcb_components.json` to `electrical/s3_interface/pcb_components.json`, regenerate the schematic and XML netlist, then run `docker exec energyline-kicad python3 /project/build_rev_a.py`. Rerun DRC, ERC and simulation after any design change, and regenerate manufacturing files from the checked board. Native KiCad footprints are taken from the installed KiCad 10.0.3 library.
