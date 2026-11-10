import json, math, unittest, xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DesignEvidenceTests(unittest.TestCase):
    def test_dimensioned_drawings_are_valid_svg(self):
        for path in (ROOT / "cad").rglob("*.svg"):
            root = ET.parse(path).getroot()
            self.assertTrue(root.tag.endswith("svg"))
            self.assertIn("CONCEPT ONLY", path.read_text())

    def test_tolerance_arithmetic_and_hole_locations(self):
        dims = json.loads((ROOT / "cad/dimensions.json").read_text())
        t = dims["tolerance_assumptions"]
        stack = dims["tolerance_stack"]
        per_axis = (
            t["tray_hole_position_plus_minus"]
            + t["cover_hole_position_plus_minus"]
            + t["locator_repeatability_plus_minus"]
        )
        self.assertAlmostEqual(stack["per_axis_worst_case"], per_axis)
        self.assertAlmostEqual(
            stack["in_plane_worst_case"], math.hypot(per_axis, per_axis)
        )
        clearance = (
            dims["cover_hole_diameter"]
            - t["cover_hole_diameter_plus_minus"]
            - t["mock_fastener_diameter"]
        ) / 2
        self.assertAlmostEqual(stack["minimum_radial_clearance"], clearance)
        self.assertGreater(clearance - stack["in_plane_worst_case"], 0)
        self.assertGreater(
            math.hypot(0.5, 0.5), (4.5 - 0.15 - 3) / 2
        )  # Original hole size had insufficient radial margin.
        for x, y in dims["fastener_centres"]:
            self.assertTrue(0 < x < dims["tray"][0] and 0 < y < dims["tray"][1])

    def test_dxf_units_and_expected_layers(self):
        data = (ROOT / "cad/layout/line_layout.dxf").read_text()
        self.assertIn("$INSUNITS\n70\n4", data)
        for name in ("S1", "S2", "S3", "S4", "S5", "REWORK", "MATERIAL", "AISLE"):
            self.assertIn("8\n" + name + "\n", data)


if __name__ == "__main__":
    unittest.main()
