import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src/simulation"), str(ROOT / "src/analysis")]
from finite_buffers import simulate
from process_times import validate_timing, sample_duration
from variability_experiments import wilson_interval, percentile


class VariabilityTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "configs/variable_times.json").read_text())

    def test_reproducible_and_seed_changes_trace(self):
        result = simulate(self.config)
        self.assertEqual(result, simulate(self.config))
        self.config["seed"] += 1
        self.assertNotEqual(result[0], simulate(self.config)[0])

    def test_zero_variation_matches_fixed(self):
        self.config["processing_time"]["relative_half_width"] = 0
        events, result, _ = simulate(self.config)
        self.config["processing_time"] = {"distribution": "fixed"}
        fixed_events, fixed, _ = simulate(self.config)
        self.assertEqual(events, fixed_events)
        self.assertEqual(result["accepted_units"], fixed["accepted_units"])
        self.assertEqual(
            result["time_weighted_mean_wip"], fixed["time_weighted_mean_wip"]
        )

    def test_sample_bounds_and_pairing(self):
        timing = validate_timing(self.config)
        station = self.config["stations"][2]
        other = copy.deepcopy(self.config)
        other["operator_count"] = 5
        for unit in range(100):
            duration = sample_duration(self.config, timing, station, str(unit))
            self.assertTrue(120 <= duration <= 180)
            self.assertEqual(
                duration, sample_duration(other, timing, station, str(unit))
            )

    def test_stochastic_invariants(self):
        for seed in range(5):
            self.config["seed"] = seed
            events, result, snapshots = simulate(self.config)
            active = {}
            accepted = []
            for event in events:
                operator = event["operator_id"]
                if event["event_type"] == "started":
                    self.assertNotIn(operator, active)
                    active[operator] = event["unit_id"]
                elif event["event_type"] == "completed":
                    self.assertEqual(active.pop(operator), event["unit_id"])
                elif event["event_type"] == "accepted":
                    accepted.append(event["unit_id"])
                self.assertLessEqual(
                    event["timestamp_s"], result["production_window_s"]
                )
            self.assertEqual(len(accepted), len(set(accepted)))
            for snap in snapshots:
                self.assertTrue(all(q <= 2 for q in snap["queue_lengths"]))
                self.assertEqual(
                    snap["released_units"] - snap["accepted_units"],
                    sum(snap["queue_lengths"])
                    + sum(u is not None for u in snap["station_units"]),
                )

    def test_invalid_inputs(self):
        for width in (-0.1, 1, float("nan"), True, None):
            self.config["processing_time"]["relative_half_width"] = width
            with self.assertRaises(ValueError):
                simulate(self.config)
        self.config["processing_time"]["relative_half_width"] = 0.2
        self.config["seed"] = None
        with self.assertRaises(ValueError):
            simulate(self.config)

    def test_summary_statistics(self):
        low, high = wilson_interval(0, 30)
        self.assertAlmostEqual(low, 0)
        self.assertAlmostEqual(high, 0.1135133931739688)
        self.assertAlmostEqual(wilson_interval(30, 30)[0], 1 - high)
        self.assertEqual(percentile([10, 20, 30], 0.5), 20)
        self.assertEqual(percentile([10, 20, 30], 0.05), 11)


if __name__ == "__main__":
    unittest.main()
