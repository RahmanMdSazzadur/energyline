import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/simulation"))
from finite_buffers import simulate
from multi_unit import simulate as unlimited


class FiniteBufferTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "configs/finite_baseline.json").read_text())

    def check_invariants(self, config):
        events, summary, snapshots = simulate(config)
        accepted = [e["unit_id"] for e in events if e["event_type"] == "accepted"]
        self.assertEqual(len(accepted), len(set(accepted)))
        for snap in snapshots:
            self.assertTrue(
                all(
                    0 <= size <= cap
                    for size, cap in zip(
                        snap["queue_lengths"], config["buffer_capacities"]
                    )
                )
            )
            physical_wip = sum(u is not None for u in snap["station_units"]) + sum(
                snap["queue_lengths"]
            )
            self.assertEqual(
                snap["released_units"] - snap["accepted_units"], physical_wip
            )
        for station in summary["stations"]:
            self.assertAlmostEqual(
                sum(
                    station[k]
                    for k in [
                        "productive_time_s",
                        "blocked_time_s",
                        "starved_time_s",
                        "waiting_for_operator_time_s",
                    ]
                ),
                summary["production_window_s"],
            )
        # Reconcile FIFO and exclusive processing from the trace.
        for station in config["stations"]:
            active = None
            starts = []
            for event in events:
                if event["station_id"] != station["id"]:
                    continue
                if event["event_type"] == "started":
                    self.assertIsNone(active)
                    active = event["unit_id"]
                    starts.append(active)
                elif event["event_type"] == "completed":
                    self.assertEqual(active, event["unit_id"])
                    active = None
            self.assertEqual(starts, sorted(starts))
        return events, summary, snapshots

    def test_finite_baseline_and_blocking(self):
        _, summary, _ = self.check_invariants(self.config)
        self.assertEqual(summary["accepted_units"], 165)
        self.assertLessEqual(summary["unfinished_units"], 5 + 8)
        self.assertGreater(summary["stations"][0]["blocked_time_s"], 0)
        self.assertEqual(summary["stations"][-1]["blocked_time_s"], 0)

    def test_zero_capacity_direct_handoff(self):
        self.config["buffer_capacities"] = [0] * 4
        _, summary, _ = self.check_invariants(self.config)
        self.assertEqual(summary["accepted_units"], 165)
        self.assertLessEqual(summary["unfinished_units"], 5)

    def test_large_buffers_match_unlimited_reference(self):
        self.config["buffer_capacities"] = [1000] * 4
        _, summary, _ = self.check_invariants(self.config)
        events, reference = unlimited(self.config)
        self.assertEqual(summary["accepted_units"], reference["accepted_units"])
        self.assertEqual(summary["unfinished_units"], reference["unfinished_units"])
        self.assertAlmostEqual(
            summary["time_weighted_mean_wip"], reference["time_weighted_mean_wip"]
        )

    def test_boundary_and_no_overtime(self):
        for duration, expected in [(44, 0), (45, 0), (464, 0), (465, 1), (615, 2)]:
            self.config["shift_duration_s"] = duration + 3600
            events, summary, _ = self.check_invariants(self.config)
            self.assertEqual(summary["accepted_units"], expected)
            self.assertTrue(all(e["timestamp_s"] <= duration for e in events))
            self.assertTrue(
                all(
                    e["timestamp_s"] < duration
                    for e in events
                    if e["event_type"] == "started"
                )
            )

    def test_varied_small_lines(self):
        for durations in ([1, 1], [1, 3], [3, 1], [2, 7, 3], [7, 2, 3]):
            for capacity in (0, 1, 2):
                config = copy.deepcopy(self.config)
                config["stations"] = [
                    {"id": f"S{i}", "mean_process_s": d}
                    for i, d in enumerate(durations)
                ]
                config["buffer_capacities"] = [capacity] * (len(durations) - 1)
                config["shift_duration_s"] = 3650
                self.check_invariants(config)

    def test_invalid_buffer_configuration(self):
        for capacities in (
            None,
            [],
            [1],
            [1, 2, -1, 2],
            [True, 2, 2, 2],
            [1.5, 2, 2, 2],
        ):
            self.config["buffer_capacities"] = capacities
            with self.assertRaises(ValueError):
                simulate(self.config)

    def test_repeatable(self):
        self.assertEqual(simulate(self.config), simulate(self.config))


if __name__ == "__main__":
    unittest.main()
