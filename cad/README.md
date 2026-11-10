# Concept CAD and layout

Regenerate with `python3 scripts/build_designs.py`.

- `product/module.scad`: editable OpenSCAD inert tray, inserts, bosses and exploded lid.
- `fixture/locating_fixture.scad`: editable locating/support/contact/clamp concept.
- `product/module_dimensioned.svg`, `fixture/fixture_dimensioned.svg`: dimensioned top-view drawings and tolerance assumptions.
- `layout/line_layout.dxf`: 2D CAD layout in mm with operation, buffer, aisle, material and rework layers.
- `layout/line_layout.svg`: readable concept plan.
- `dimensions.json`: nominal geometry and worst-case tolerance arithmetic.

These are concept models, not fabrication-ready or certified machinery designs. OpenSCAD source has not been compiled in this environment. The fixture uses a 3-2-1 datum concept with replaceable contacts. Clamp forces, sensor brackets, material deflection, thermal effects, real fastener tolerances, maintainability and guarding require engineering validation. A parallel S3 fixture needs a revised station footprint; the displayed layout is the five-operation single-cell concept.
