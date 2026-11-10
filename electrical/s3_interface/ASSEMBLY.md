# EnergyLine S3 — Revision A

80 × 70 mm, two-layer, through-hole bench interface. This revision is intended for a manufactured PCB with plated through-holes and hand assembly. It drives one red LED and reads two external dry contacts. It does not operate a real clamp.

## Parts and mechanical fit

Use `assembly_bom.csv` for values, footprints and physical dimensions. Resistors use DIN0207 bodies and 7.62 mm formed lead spacing. Capacitors use 5.00 mm lead spacing and bodies no larger than the selected 5 mm disc footprint. All headers are 2.54 mm pitch. The BC547B uses the wide TO-92 footprint: form the leads gently to 2.54 mm spacing. Match the flat face shown on the assembly drawing.

F1 is a soldered Littelfuse 372-series 100 mA time-lag radial fuse, nominal 5.08 mm lead spacing (candidate 37201000001). It is not a replaceable cartridge holder. Check the ordered part's dimensions before assembly. Its cold resistance differs from the illustrative 1 ohm SPICE fuse model; fuse operation is not simulated.

D1 uses standard LED numbering: pad 1 is cathode (flat body side/short lead), pad 2 is anode. This numbering has been corrected consistently in the schematic, netlist and simulation. Q1 uses collector/base/emitter on pins 1/2/3, respectively. Do not substitute a different transistor without checking its pinout.

Four 3.2 mm non-plated mounting holes are centered 5 mm from the board corners, giving 70 × 60 mm center spacing. Use insulating standoffs. Verify enclosure fit before ordering.

## Connections

| Header | Pin | Signal |
|---|---|---|
| J1 | 1 | Regulated +5 V input |
| J1 | 2 | Ground |
| J2 | 1 | Fused +5 V rail |
| J2 | 2 | Ground |
| J2 | 3 | CLAMP_CMD: 5 V logic output from external controller |
| J2 | 4 | PART_N: active-low input to external controller |
| J2 | 5 | COVER_N: active-low input to external controller |
| J2 | 6 | PERMIT_OK: permit rail status to external controller |
| J3 | 1 / 2 | PART_N / GND; external dry contact closes for presence |
| J4 | 1 / 2 | COVER_N / GND; external dry contact closes for presence |
| SW1 | 1 / 2 | Fused +5 V / permit rail; external SPST switch |
| TP1 | 1 | Q1 collector voltage probe |

SW1 is deliberately implemented as a header for an external switch, rather than an unspecified on-board switch footprint. Closing it permits LED power. This is an instructional permit function, not a certified safety interlock.

Use a single regulated 5 V supply and a controller with 5 V-compatible input/output pins. The inputs are pulled up to 5 V and are not directly suitable for an unprotected 3.3 V controller. Do not connect independent J1 and J2 power supplies together or backfeed a USB-powered controller. The board does not include reverse-polarity protection or voltage regulation.

## Assembly and first power-up

1. Inspect the bare PCB and verify there are no visible bridges or damaged holes.
2. Fit resistors first, followed by capacitors, fuse, transistor, LED and headers. Observe LED and transistor orientation. Leave external wiring disconnected while soldering.
3. Check solder joints and continuity with the board unpowered. Verify no low-resistance short exists between the power input and ground. Verify connector pin numbering against the drawing.
4. Apply a current-limited, regulated 5 V source to J1, with the permit open and command held at ground. Start with a low limit suitable for the approximately 6 mA demonstration circuit, such as 20 mA, without powering an external controller from this board.
5. Verify the fused rail is close to 5 V. Close the permit: PERMIT_OK should rise. The LED must remain off with command low.
6. Drive CLAMP_CMD high from a compatible source sharing ground: the LED should light at roughly 4 mA. Open the permit while command remains high: the LED must turn off.
7. Check J3/J4 inputs are high when open and low when shorted to their adjacent ground pin. Their RC filtering is not full switch debouncing.
8. Remove power before changing any wiring. Record actual supply voltage, LED current, collector voltage and contact input voltages; simulation is not a replacement for these measurements.

## Fabrication intent and limits

Two copper layers, nominal 1.6 mm FR-4 and 1 oz copper, solder mask both sides, front silkscreen. Routing uses 0.35 mm tracks, 0.25 mm minimum design clearance, and 0.8/0.4 mm via diameter/drill. Confirm these values with the chosen fabricator. Holes are plated except the four mounting holes. No impedance control is required for this low-speed circuit.

This is an engineering prototype, not an industry-certified product. KiCad DRC and schematic parity reports provide layout checks; they do not demonstrate EMC, ESD, environmental durability, fuse selectivity or physical reliability. Dry contacts and ideal logic were used in the transient simulation. Build and measure a prototype before treating the design as proven.

## References

- onsemi BC547 family: https://www.onsemi.com/download/data-sheet/pdf/bc546-d.pdf
- Littelfuse 372 series: https://www.littelfuse.com/products/fuses-overcurrent-protection/fuses/axial-radial-thru-hole-fuses/tr5-fuses/372
- Manufacturer 372 datasheet: https://www.littelfuse.com/assetdocs/littelfuse-fuse-372-datasheet?assetguid=1a83e408-fdbe-48de-8389-c4f8ebb8232e

Footprints are embedded from the KiCad library installed in the KiCad 10.0.3 container. Review the actual component dimensions before purchasing substitutions.

## Fuse visualization

The fuse now uses a local simplified dimensional envelope. Its dimensions come from the manufacturer datasheet, but it is not manufacturer CAD and does not establish actual part or enclosure fit. See models/README.md.
