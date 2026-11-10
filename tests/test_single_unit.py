import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/simulation"))
from single_unit import simulate


class SingleUnitTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "configs/baseline.json").read_text())

    def test_reference_timing_and_single_acceptance(self):
        events, summary = simulate(self.config)
        self.assertEqual(summary["completion_time_s"], 465)
        self.assertEqual(
            [e["timestamp_s"] for e in events if e["event_type"] == "completed"],
            [45, 165, 315, 405, 465],
        )
        self.assertEqual(sum(e["event_type"] == "accepted" for e in events), 1)
        self.assertEqual(
            summary["released_units"],
            summary["accepted_units"]
            + summary["scrapped_units"]
            + summary["unfinished_units"],
        )

    def test_shift_cutoff_leaves_unit_unfinished(self):
        self.config["shift_duration_s"] = 3800
        events, summary = simulate(self.config)
        self.assertEqual(summary["accepted_units"], 0)
        self.assertEqual(summary["unfinished_units"], 1)
        self.assertIsNone(summary["completion_time_s"])
        self.assertEqual(events[-1]["timestamp_s"], 200)
        self.assertFalse(any(e["event_type"] == "accepted" for e in events))

    def test_exact_shift_boundary_counts_completion(self):
        self.config["shift_duration_s"] = 4065
        _, summary = simulate(self.config)
        self.assertEqual(summary["accepted_units"], 1)

    def test_invalid_times_rejected(self):
        for duration in [-1, 0, float("nan"), float("inf")]:
            config = copy.deepcopy(self.config)
            config["stations"][0]["mean_process_s"] = duration
            with self.assertRaises(ValueError):
                simulate(config)


if __name__ == "__main__":
    unittest.main()
