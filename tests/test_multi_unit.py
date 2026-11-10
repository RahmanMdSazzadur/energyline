import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/simulation"))
from multi_unit import simulate


class MultiUnitTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "configs/baseline.json").read_text())

    def test_analytical_baseline_and_conservation(self):
        events, result = simulate(self.config)
        completions = [e for e in events if e["event_type"] == "accepted"]
        self.assertEqual(
            [e["timestamp_s"] for e in completions], list(range(465, 25201, 150))
        )
        self.assertEqual(result["accepted_units"], 165)
        self.assertEqual(result["released_units"], 560)
        self.assertEqual(result["unfinished_units"], 395)
        self.assertEqual(len({e["unit_id"] for e in completions}), 165)
        self.assertEqual(
            result["released_units"],
            result["accepted_units"] + result["unfinished_units"],
        )
        self.assertEqual(
            [e["timestamp_s"] for e in events], sorted(e["timestamp_s"] for e in events)
        )

    def test_station_never_processes_two_units_at_once(self):
        events, _ = simulate(self.config)
        for station in self.config["stations"]:
            active = None
            for event in events:
                if event["station_id"] != station["id"]:
                    continue
                if event["event_type"] == "started":
                    self.assertIsNone(active)
                    active = event["unit_id"]
                elif event["event_type"] in ("completed", "shift_ended"):
                    self.assertEqual(active, event["unit_id"])
                    active = None

    def test_shift_boundary(self):
        for horizon, expected in [(464, 0), (465, 1), (615, 2)]:
            self.config["shift_duration_s"] = 3600 + horizon
            events, result = simulate(self.config)
            self.assertEqual(result["accepted_units"], expected)
            self.assertTrue(all(0 <= e["timestamp_s"] <= horizon for e in events))

    def test_other_bottleneck_and_queue_growth(self):
        self.config["stations"][2]["mean_process_s"] = 70
        _, result = simulate(self.config)
        self.assertEqual(result["accepted_units"], 207)
        self.assertGreater(result["stations"][1]["peak_waiting_units"], 0)
        self.assertEqual(result["stations"][2]["peak_waiting_units"], 0)

    def test_repeatable_and_wip_accounting(self):
        events, result = simulate(self.config)
        self.assertEqual((events, result), simulate(self.config))
        population = 0
        area = 0
        last = 0
        for event in events:
            area += population * (event["timestamp_s"] - last)
            last = event["timestamp_s"]
            population += (event["event_type"] == "released") - (
                event["event_type"] == "accepted"
            )
        area += population * (result["production_window_s"] - last)
        self.assertEqual(population, result["unfinished_units"])
        self.assertAlmostEqual(
            area / result["production_window_s"], result["time_weighted_mean_wip"]
        )


if __name__ == "__main__":
    unittest.main()
