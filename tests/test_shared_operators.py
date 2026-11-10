import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/simulation"))
from finite_buffers import simulate


class SharedOperatorTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "configs/shared_operators.json").read_text())

    def test_no_overlapping_operator_tasks_and_time_accounting(self):
        for count in (1, 2, 3, 5):
            self.config["operator_count"] = count
            events, summary, snapshots = simulate(self.config)
            active = {}
            work = [0] * count
            for event in events:
                operator = event["operator_id"]
                if event["event_type"] == "started":
                    self.assertNotIn(operator, active)
                    self.assertIn(operator, range(count))
                    active[operator] = (event["unit_id"], event["timestamp_s"])
                elif event["event_type"] == "completed":
                    unit, start = active.pop(operator)
                    self.assertEqual(unit, event["unit_id"])
                    work[operator] += event["timestamp_s"] - start
            for operator, (_, start) in active.items():
                work[operator] += summary["production_window_s"] - start
            for operator, metrics in enumerate(summary["operators"]):
                self.assertEqual(work[operator], metrics["productive_time_s"])
                self.assertLessEqual(work[operator], summary["production_window_s"])
            for snap in snapshots:
                operators = [o for o in snap["station_operators"] if o is not None]
                self.assertEqual(len(operators), len(set(operators)))
                self.assertLessEqual(len(operators), count)
                self.assertEqual(
                    snap["released_units"] - snap["accepted_units"],
                    sum(snap["queue_lengths"])
                    + sum(u is not None for u in snap["station_units"]),
                )
            self.assertAlmostEqual(
                sum(work), sum(s["productive_time_s"] for s in summary["stations"])
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

    def test_one_operator_matches_sequential_work_bound(self):
        self.config["operator_count"] = 1
        events, summary, _ = simulate(self.config)
        self.assertEqual(summary["accepted_units"], 54)
        self.assertEqual(
            [e["timestamp_s"] for e in events if e["event_type"] == "accepted"],
            list(range(465, 25201, 465)),
        )
        self.assertEqual(summary["paid_labor_hours"], 8)

    def test_five_operators_reproduce_dedicated_baseline(self):
        self.config["operator_count"] = 5
        _, shared, _ = simulate(self.config)
        dedicated_config = copy.deepcopy(self.config)
        del dedicated_config["operator_count"]
        _, dedicated, _ = simulate(dedicated_config)
        for key in [
            "accepted_units",
            "released_units",
            "unfinished_units",
            "time_weighted_mean_wip",
        ]:
            self.assertEqual(shared[key], dedicated[key])

    def test_short_shift_and_zero_buffers(self):
        for count in (1, 2, 3):
            self.config.update(
                operator_count=count, buffer_capacities=[0] * 4, shift_duration_s=4065
            )
            events, summary, _ = simulate(self.config)
            self.assertEqual(summary["accepted_units"], 1)
            self.assertTrue(
                all(
                    e["timestamp_s"] < 465
                    for e in events
                    if e["event_type"] == "started"
                )
            )

    def test_invalid_staffing(self):
        for count in (0, -1, 1.5, True, None):
            self.config["operator_count"] = count
            with self.assertRaises(ValueError):
                simulate(self.config)


if __name__ == "__main__":
    unittest.main()
