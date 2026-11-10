import copy, json, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/simulation"))
from finite_buffers import simulate
from cell_adapter import execute_cycle, validate_adapter


class AdapterTests(unittest.TestCase):
    def config(self):
        return json.loads((ROOT / "configs/integrated_s3.json").read_text())

    def test_linked_ids_and_conservation(self):
        c = self.config()
        c["shift_duration_s"] = 5600
        events, result, _ = simulate(c)
        self.assertTrue(result["cell_integration"]["enabled"])
        cycles = result["cell_integration"]["cycles"]
        self.assertEqual(len(cycles), len({v["unit_id"] for v in cycles}))
        self.assertEqual(
            result["released_units"],
            result["accepted_units"]
            + result["scrapped_units"]
            + result["unfinished_units"],
        )
        self.assertEqual(
            len(cycles), sum(e["event_type"] == "cell_cycle_linked" for e in events)
        )

    def test_forced_normal_fail_and_fault(self):
        c = self.config()
        station = next(s for s in c["stations"] if s["id"] == "S3")
        for p_fail, p_fault, expected in [
            (0, 0, "pass"),
            (1, 0, "fail"),
            (0, 1, "quarantined"),
        ]:
            station["cell_adapter"].update(
                failed_result_probability=p_fail, fault_probability=p_fault
            )
            cycle = execute_cycle(c, station, "linked-001", 70)
            self.assertEqual(cycle["outcome"], expected)
            self.assertTrue(cycle["trace"]["passed"])
            self.assertIn("linked-001", cycle["trace"]["journal"]["units"])
            if expected == "pass":
                self.assertAlmostEqual(cycle["line_duration_s"], 70)

    def test_quarantined_units_never_become_good(self):
        c = self.config()
        station = next(s for s in c["stations"] if s["id"] == "S3")
        station["cell_adapter"] = {
            "fault_probability": 1,
            "failed_result_probability": 0,
        }
        c["shift_duration_s"] = 5600
        events, result, _ = simulate(c)
        self.assertEqual(result["accepted_units"], 0)
        self.assertGreater(result["scrapped_units"], 0)
        self.assertEqual(
            sum(e["event_type"] == "cell_quarantined" for e in events),
            result["scrapped_units"],
        )

    def test_ambiguous_double_failure_model_rejected(self):
        c = self.config()
        next(s for s in c["stations"] if s["id"] == "S3")["reliability"] = {
            "mtbf_s": 100,
            "repair_mean_s": 10,
        }
        with self.assertRaises(ValueError):
            validate_adapter(c)


if __name__ == "__main__":
    unittest.main()
