# S3 Revision A — routed engineering prototype

The current board is S3_interface.kicad_pcb. It replaces the unrouted placement study. It contains 18 electrical components, four M3 mounting holes, 40 connected component pads and one through-via on two copper layers. Its dimensions are 80 × 70 mm. Standard KiCad library footprints replace all provisional patterns.

KiCad 10.0.3 checks completed with zero configured DRC warnings/errors, zero unconnected items and zero schematic parity issues. Schematic ERC completed with zero reported violations. The ngspice transient simulation passed 12/12 functional checks. Reports preserve KiCad's list of default ignored checks; no findings were excluded to obtain a pass.

Manufacturing outputs are in fabrication/rev_A. Read ASSEMBLY.md and assembly_bom.csv before buying parts or ordering a prototype. Match the specified lead spacings and transistor/LED pinout. External permit and presence switches connect through headers.

This revision is a prototype design ready for fabrication review, not an industry-certified or physically validated product. Actual purchased parts, enclosure fit and a built prototype remain unverified. No EMC/ESD, environmental or safety certification has been performed.

The combined release includes only the current S3_interface board. The earlier unrouted placement study is excluded.

The missing fuse visualization has been replaced by a local simplified dimensional envelope, documented in models/README.md. It renders successfully in KiCad; the subsequent DRC and schematic parity check still reports zero findings. This visualization does not verify actual component or enclosure fit.
