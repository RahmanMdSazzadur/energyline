"""Generate editable concept CAD, 2D DXF and dimensioned SVG. Units: mm."""

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def svg_start(title, width=960, height=660):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><rect width="100%" height="100%" fill="#f6f5ee"/><g font-family="Arial,sans-serif" fill="#243d31"><text x="35" y="44" font-size="24" font-weight="bold">{title}</text><text x="35" y="70" font-size="12">CONCEPT ONLY · dimensions in mm · not a manufacturing release</text>'


def rect(x, y, w, h, color="#c4d1b7", stroke="#456440"):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{color}" stroke="{stroke}" stroke-width="1.5"/>'


def text(x, y, value, size=14):
    return f'<text x="{x}" y="{y}" font-size="{size}">{value}</text>'


def dimension(x1, y1, x2, y2, label):
    return (
        f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="#b76f3e" stroke-width="1.5"/><circle cx="{x1}" cy="{y1}" r="3" fill="#b76f3e"/><circle cx="{x2}" cy="{y2}" r="3" fill="#b76f3e"/>'
        + text((x1 + x2) / 2 + 6, (y1 + y2) / 2 - 7, label, 13)
    )


def write_dxf(path, rectangles):
    lines = [
        "0",
        "SECTION",
        "2",
        "HEADER",
        "9",
        "$INSUNITS",
        "70",
        "4",
        "0",
        "ENDSEC",
        "0",
        "SECTION",
        "2",
        "ENTITIES",
    ]
    for name, x, y, w, h in rectangles:
        for a, b in [
            ((x, y), (x + w, y)),
            ((x + w, y), (x + w, y + h)),
            ((x + w, y + h), (x, y + h)),
            ((x, y + h), (x, y)),
        ]:
            lines += [
                "0",
                "LINE",
                "8",
                name,
                "10",
                str(a[0]),
                "20",
                str(a[1]),
                "30",
                "0",
                "11",
                str(b[0]),
                "21",
                str(b[1]),
                "31",
                "0",
            ]
    lines += ["0", "ENDSEC", "0", "EOF"]
    path.write_text("\n".join(lines) + "\n")


def main():
    product = ROOT / "cad/product"
    fixture = ROOT / "cad/fixture"
    layout = ROOT / "cad/layout"
    for folder in (product, fixture, layout):
        folder.mkdir(parents=True, exist_ok=True)
    dimensions = {
        "units": "mm",
        "tray": [180, 120, 30],
        "wall": 3,
        "floor": 4,
        "cover_thickness": 3,
        "insert": [30, 80, 20],
        "insert_x": [12, 54, 96, 138],
        "insert_y": 20,
        "fastener_centres": [[12, 12], [168, 12], [12, 108], [168, 108]],
        "cover_hole_diameter": 5.0,
        "fixture_base": [240, 180, 12],
        "tray_origin_on_fixture": [30, 30],
        "tolerance_assumptions": {
            "tray_width_plus_minus": 0.5,
            "cover_width_plus_minus": 0.3,
            "tray_hole_position_plus_minus": 0.2,
            "cover_hole_position_plus_minus": 0.2,
            "locator_repeatability_plus_minus": 0.1,
            "cover_hole_diameter_plus_minus": 0.15,
            "mock_fastener_diameter": 3,
        },
        "tolerance_stack": {
            "per_axis_worst_case": 0.5,
            "in_plane_worst_case": math.hypot(0.5, 0.5),
            "minimum_radial_clearance": 0.925,
            "remaining_assumed_margin": 0.925 - math.hypot(0.5, 0.5),
        },
    }
    (ROOT / "cad/dimensions.json").write_text(json.dumps(dimensions, indent=2) + "\n")
    product.joinpath("module.scad").write_text(
        """// EnergyLine inert module concept. mm. Not manufacturing qualified.
$fn=48;
tray=[180,120,30]; wall=3; floor_t=4; cover_t=3;
centres=[[12,12],[168,12],[12,108],[168,108]];
module base_tray(){
 difference(){
  union(){difference(){cube(tray);translate([wall,wall,floor_t])cube([174,114,31]);}
   for(p=centres)translate([p[0],p[1],4])cylinder(h=26,r=5);}
  for(p=centres)translate([p[0],p[1],-1])cylinder(h=32,d=3.5);
 }
}
module lid(){difference(){cube([180,120,cover_t]);for(p=centres)translate([p[0],p[1],-1])cylinder(h=5,d=5.0);}}
color([.48,.65,.44])base_tray();
for(x=[12,54,96,138])color([.25,.4,.3])translate([x,20,4])cube([30,80,20]);
color([.8,.86,.73,.6])translate([0,0,45])lid(); // exploded cover, assembled z=30
"""
    )
    fixture.joinpath("locating_fixture.scad").write_text(
        """// Fixture concept, mm. Replaceable contacts; low-force virtual clamp blocks.
$fn=32;
color([.65,.72,.59])cube([240,180,12]);
// Datum A: support pads. B: two contacts on long edge. C: one short-edge stop.
for(p=[[50,50],[190,50],[120,130]])color([.4,.55,.35])translate([p[0],p[1],12])cylinder(h=3,d=12);
for(x=[65,175])color([.75,.48,.25])translate([x-5,26,12])cube([10,4,12]);
color([.75,.48,.25])translate([26,85,12])cube([4,10,12]);
// Adjustable opposed clamp concept. No real force or safety rating is specified.
for(x=[10,214])color([.7,.4,.2])translate([x,75,12])cube([16,30,18]);
"""
    )
    s = svg_start("EnergyLine / Mock module — top and section")
    ox, oy, scale = 100, 125, 3
    s += rect(ox, oy, 540, 360)
    for x in dimensions["insert_x"]:
        s += rect(ox + x * scale, oy + 60, 90, 240, "#6d8b62")
    for x, y in dimensions["fastener_centres"]:
        s += f'<circle cx="{ox+x*scale}" cy="{oy+y*scale}" r="7.5" fill="#f6f5ee" stroke="#a6643b"/>'
    s += dimension(100, 105, 640, 105, "180 ±0.5 tray") + dimension(
        75, 125, 75, 485, "120"
    )
    s += (
        text(690, 150, "4 identical inert inserts", 16)
        + text(690, 176, "30 × 80 × 20")
        + text(690, 215, "Tray height 30; floor 4")
    )
    s += (
        text(690, 250, "Cover thickness 3")
        + text(690, 285, "4 × Ø5.0 ±0.15 holes")
        + text(690, 320, "Centres: 12 / 168 × 12 / 108", 12)
    )
    s += text(
        100,
        530,
        "Section: base floor 4 + inserts 20; cover at z=30. No energized components.",
        14,
    )
    s += text(
        100,
        560,
        "Position error: 0.5 per axis; radial worst case sqrt(0.5² + 0.5²) = 0.707.",
        12,
    )
    s += text(
        100,
        585,
        "Minimum radial clearance (4.85 - 3.00)/2 = 0.925; assumed radial margin = 0.218.",
        12,
    )
    s += "</g></svg>"
    product.joinpath("module_dimensioned.svg").write_text(s)
    s = svg_start("EnergyLine / S3 locating fixture — datum concept")
    sc = 2.4
    ox = 120
    oy = 115
    s += rect(ox, oy, 240 * sc, 180 * sc)
    s += rect(ox + 30 * sc, oy + 30 * sc, 180 * sc, 120 * sc, "#e1e8d7")
    for x, y in [(50, 50), (190, 50), (120, 130)]:
        s += f'<circle cx="{ox+x*sc}" cy="{oy+y*sc}" r="14" fill="#809d6a"/>'
    for x in (65, 175):
        s += rect(ox + (x - 5) * sc, oy + 26 * sc, 10 * sc, 4 * sc, "#ce8248")
    s += rect(ox + 26 * sc, oy + 85 * sc, 4 * sc, 10 * sc, "#ce8248")
    for x in (10, 214):
        s += rect(ox + x * sc, oy + 75 * sc, 16 * sc, 30 * sc, "#bf7542")
    s += dimension(120, 95, 696, 95, "240") + dimension(95, 115, 95, 547, "180")
    s += (
        text(735, 160, "A · 3 support pads")
        + text(735, 200, "B · 2 long-edge contacts")
        + text(735, 240, "C · 1 short-edge stop")
    )
    s += text(735, 290, "Floating clamp concept", 12) + text(
        735, 320, "Replaceable contact pads", 12
    )
    s += text(
        120,
        590,
        "3-2-1 locating concept; clear loading orientation. Base thickness 12 mm.",
        13,
    )
    s += text(
        120,
        615,
        "Clamp travel/force, guarding and fabrication tolerances require real design validation.",
        12,
    )
    s += "</g></svg>"
    fixture.joinpath("fixture_dimensioned.svg").write_text(s)
    rectangles = [
        ("BOUNDARY", 0, 0, 6200, 3600),
        ("S1", 300, 300, 1000, 700),
        ("S2", 1700, 300, 1000, 700),
        ("S3", 3100, 300, 1000, 700),
        ("S4", 4500, 300, 1000, 700),
        ("S5", 4500, 2300, 1000, 700),
        ("REWORK", 2900, 2300, 1000, 700),
        ("MATERIAL", 300, 2300, 1000, 700),
        ("B12", 1350, 450, 300, 300),
        ("B23", 2750, 450, 300, 300),
        ("B34", 4150, 450, 300, 300),
        ("B45", 4750, 1500, 300, 300),
        ("AISLE", 300, 1100, 5200, 1000),
    ]
    write_dxf(layout / "line_layout.dxf", rectangles)
    s = svg_start("EnergyLine / Five-operation U-layout — spatial concept", 1120, 760)
    for name, x, y, w, h in rectangles:
        color = (
            "#eef1e7"
            if name == "BOUNDARY"
            else (
                "#f5e6d1"
                if name == "AISLE"
                else "#c0d0af" if name.startswith("S") else "#dce4d2"
            )
        )
        s += rect(50 + x * 0.16, 110 + y * 0.16, w * 0.16, h * 0.16, color)
        s += text(
            57 + x * 0.16,
            130 + y * 0.16,
            name.replace("AISLE", "1000 mm clear aisle (assumed)"),
            11,
        )
    s += text(
        52,
        718,
        "Overall 6200 × 3600 mm. Service access, materials and rework shown; two-unit buffers assumed.",
        12,
    )
    s += text(
        52,
        742,
        "Operator travel is not included in flow times. Aisle and guarding dimensions are planning assumptions, not compliance claims.",
        11,
    )
    s += "</g></svg>"
    layout.joinpath("line_layout.svg").write_text(s)
    (ROOT / "cad/README.md").write_text("""# Concept CAD and layout

Regenerate with `python3 scripts/build_designs.py`.

- `product/module.scad`: editable OpenSCAD inert tray, inserts, bosses and exploded lid.
- `fixture/locating_fixture.scad`: editable locating/support/contact/clamp concept.
- `product/module_dimensioned.svg`, `fixture/fixture_dimensioned.svg`: dimensioned top-view drawings and tolerance assumptions.
- `layout/line_layout.dxf`: 2D CAD layout in mm with operation, buffer, aisle, material and rework layers.
- `layout/line_layout.svg`: readable concept plan.
- `dimensions.json`: nominal geometry and worst-case tolerance arithmetic.

These are concept models, not fabrication-ready or certified machinery designs. OpenSCAD source has not been compiled in this environment. The fixture uses a 3-2-1 datum concept with replaceable contacts. Clamp forces, sensor brackets, material deflection, thermal effects, real fastener tolerances, maintainability and guarding require engineering validation. A parallel S3 fixture needs a revised station footprint; the displayed layout is the five-operation single-cell concept.
""")
    print("Generated editable CAD concepts, dimensioned drawings and DXF layout.")


if __name__ == "__main__":
    main()
