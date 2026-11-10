import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/simulation"))
from finite_buffers import simulate


class AttendanceTests(unittest.TestCase):
    def config(self):
        return {
            "model_version": "test",
            "scenario": "attendance",
            "input_source": "synthetic",
            "shift_duration_s": 100,
            "planned_nonproduction_s": 0,
            "target_good_units": 1,
            "operator_count": 1,
            "buffer_capacities": [0],
            "stations": [
                {"id": "S1", "mean_process_s": 10},
                {"id": "S2", "mean_process_s": 20, "operator_attended_fraction": 0.25},
            ],
        }

    def test_operator_released_while_machine_continues(self):
        events, _, _ = simulate(self.config())

        def matching(station, unit, event):
            return next(
                e["timestamp_s"]
                for e in events
                if e["station_id"] == station
                and e["unit_id"] == unit
                and e["event_type"] == event
            )

        self.assertEqual(matching("S2", "UNIT-000001", "started"), 10)
        self.assertEqual(matching("S2", "UNIT-000001", "operator_released"), 15)
        self.assertEqual(matching("S2", "UNIT-000001", "completed"), 30)
        self.assertEqual(matching("S1", "UNIT-000002", "started"), 15)

    def test_exclusivity_and_labor_reconciliation(self):
        config = self.config()
        for fraction in (0, 0.25, 0.5, 1):
            config["stations"][1]["operator_attended_fraction"] = fraction
            events, result, _ = simulate(config)
            active = {}
            busy = 0
            for e in events:
                operator = e["operator_id"]
                if e["event_type"] == "started" and operator is not None:
                    self.assertNotIn(operator, active)
                    active[operator] = e["timestamp_s"]
                elif (
                    e["event_type"] in ("completed", "operator_released")
                    and operator is not None
                ):
                    busy += e["timestamp_s"] - active.pop(operator)
            busy += sum(100 - start for start in active.values())
            self.assertEqual(busy, result["operators"][0]["productive_time_s"])
            self.assertEqual(
                result["released_units"],
                result["accepted_units"] + result["unfinished_units"],
            )

    def test_shift_can_end_during_unattended_work(self):
        config = self.config()
        config["shift_duration_s"] = 18
        _, result, snaps = simulate(config)
        self.assertEqual(result["accepted_units"], 0)
        self.assertEqual(result["operators"][0]["productive_time_s"], 18)
        self.assertEqual(snaps[-1]["station_operators"], [0, None])

    def test_invalid_fraction(self):
        for fraction in (-0.1, 1.1, True, None, float("nan")):
            config = self.config()
            config["stations"][1]["operator_attended_fraction"] = fraction
            with self.assertRaises(ValueError):
                simulate(config)


if __name__ == "__main__":
    unittest.main()
