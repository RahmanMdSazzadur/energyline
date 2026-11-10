import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/analysis"))
from economics import shift_cost
from cost_comparison import build_cases


class CostTests(unittest.TestCase):
    def setUp(self):
        self.assumptions = json.loads(
            (ROOT / "configs/economics/assumptions.json").read_text()
        )
        self.deployment = {
            "components_eur": {"equipment": 10000, "fixtures": 1000},
            "power_kw": 2,
        }
        self.summary = {
            "paid_labor_hours": 32,
            "production_window_s": 25200,
            "released_units": 250,
            "rework_started_units": 10,
            "scrapped_units": 5,
            "accepted_units": 240,
        }

    def test_cost_components_reconcile(self):
        result = shift_cost(
            self.summary,
            self.assumptions,
            self.deployment,
            self.assumptions["cost_cases"]["base"],
        )
        self.assertEqual(result["deployment_total_eur"], 12650)
        breakdown = result["breakdown_eur"]
        self.assertEqual(breakdown["paid_labor"], 800)
        self.assertAlmostEqual(breakdown["energy"], 2.8)
        self.assertEqual(breakdown["consumables"], 64)
        self.assertEqual(breakdown["incremental_scrap_material_loss"], 20)
        self.assertAlmostEqual(breakdown["maintenance_allocation"], 0.8)
        self.assertAlmostEqual(breakdown["deployment_allocation"], 5.06)
        self.assertAlmostEqual(result["shift_cost_eur"], sum(breakdown.values()))
        self.assertAlmostEqual(
            result["conversion_cost_per_good_unit_eur"], result["shift_cost_eur"] / 240
        )
        self.assertIsNone(result["payback_years"])

    def test_zero_good_output_is_undefined_not_free(self):
        self.summary["accepted_units"] = 0
        result = shift_cost(
            self.summary,
            self.assumptions,
            self.deployment,
            self.assumptions["cost_cases"]["base"],
        )
        self.assertIsNone(result["conversion_cost_per_good_unit_eur"])
        self.assertGreater(result["shift_cost_eur"], 0)

    def test_no_double_counting_capital_or_reassigned_staff(self):
        case = copy.deepcopy(self.assumptions["cost_cases"]["base"])
        case["capital_multiplier"] = 2
        original = shift_cost(
            self.summary,
            self.assumptions,
            self.deployment,
            self.assumptions["cost_cases"]["base"],
        )
        doubled = shift_cost(self.summary, self.assumptions, self.deployment, case)
        self.assertEqual(
            doubled["deployment_total_eur"], 2 * original["deployment_total_eur"]
        )
        self.assertEqual(
            doubled["breakdown_eur"]["paid_labor"],
            original["breakdown_eur"]["paid_labor"],
        )
        self.assertAlmostEqual(
            doubled["shift_cost_eur"] - original["shift_cost_eur"],
            original["breakdown_eur"]["deployment_allocation"]
            + original["breakdown_eur"]["maintenance_allocation"],
        )

    def test_shared_quality_and_explicit_machine_assumptions(self):
        cases = build_cases()
        self.assertEqual(len(cases), 6)
        for case in cases:
            self.assertEqual(case["config"]["quality"], cases[0]["config"]["quality"])
            self.assertEqual(case["config"]["buffer_capacities"], [2] * 4)
        manual = cases[0]["config"]
        self.assertFalse(any(s.get("reliability") for s in manual["stations"]))
        self.assertEqual(
            sum("reliability" in s for s in cases[-1]["config"]["stations"]), 2
        )
        self.assertEqual(cases[-1]["deployment"], cases[-2]["deployment"])

    def test_invalid_cost_inputs(self):
        for key, value in [
            ("useful_life_years", 0),
            ("shifts_per_day", -1),
            ("contingency_fraction", float("nan")),
        ]:
            assumptions = copy.deepcopy(self.assumptions)
            assumptions[key] = value
            with self.assertRaises(ValueError):
                shift_cost(
                    self.summary,
                    assumptions,
                    self.deployment,
                    self.assumptions["cost_cases"]["base"],
                )


if __name__ == "__main__":
    unittest.main()
