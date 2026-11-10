import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/simulation"))
from finite_buffers import simulate


class ReliabilityTests(unittest.TestCase):
    def simple(self):
        return {
            "model_version": "test",
            "scenario": "forced_failure",
            "input_source": "synthetic",
            "shift_duration_s": 26,
            "planned_nonproduction_s": 0,
            "target_good_units": 1,
            "seed": 1,
            "operator_count": 1,
            "buffer_capacities": [],
            "stations": [
                {
                    "id": "S1",
                    "mean_process_s": 20,
                    "operator_attended_fraction": 0.5,
                    "reliability": {
                        "mtbf_s": 8,
                        "repair_mean_s": 3,
                        "uptime_distribution": "fixed",
                        "repair_distribution": "fixed",
                    },
                }
            ],
        }

    def test_exact_resume_and_attendance(self):
        events, result, _ = simulate(self.simple())
        self.assertEqual(
            [e["timestamp_s"] for e in events if e["event_type"] == "fault"], [8, 19]
        )
        self.assertEqual(
            [e["timestamp_s"] for e in events if e["event_type"] == "repaired"],
            [11, 22],
        )
        self.assertEqual(
            [
                e["timestamp_s"]
                for e in events
                if e["event_type"] == "operator_released"
            ],
            [13],
        )
        self.assertEqual(
            [e["timestamp_s"] for e in events if e["event_type"] == "accepted"], [26]
        )
        self.assertEqual(result["operators"][0]["productive_time_s"], 10)
        self.assertEqual(result["stations"][0]["fault_time_s"], 6)
        self.assertEqual(result["stations"][0]["productive_time_s"], 20)

    def test_repair_beyond_shift_does_not_complete(self):
        config = self.simple()
        config["shift_duration_s"] = 10
        events, result, _ = simulate(config)
        self.assertEqual(result["accepted_units"], 0)
        self.assertEqual(result["unfinished_units"], 1)
        self.assertEqual(result["stations"][0]["fault_time_s"], 2)
        self.assertEqual(result["operators"][0]["productive_time_s"], 8)
        self.assertFalse(any(e["event_type"] == "repaired" for e in events))

    def test_clocks_pause_between_cycles(self):
        config = self.simple()
        config["stations"][0].update(mean_process_s=5, operator_attended_fraction=1)
        events, _, _ = simulate(config)
        faults = [e for e in events if e["event_type"] == "fault"]
        self.assertEqual(faults[0]["timestamp_s"], 8)
        self.assertEqual(faults[0]["unit_id"], "UNIT-000002")

    def test_stochastic_resource_and_time_invariants(self):
        config = json.loads(
            (ROOT / "configs/scenarios/D_faster_s2_s3.json").read_text()
        )
        for station in config["stations"]:
            station["operator_attended_fraction"] = 0.5
            station["reliability"] = {"mtbf_s": 300, "repair_mean_s": 80}
        events, result, snaps = simulate(config)
        self.assertEqual((events, result, snaps), simulate(config))
        active = {}
        busy = {i: 0 for i in range(3)}
        for event in events:
            op = event["operator_id"]
            if event["event_type"] in ("started", "resumed") and op is not None:
                self.assertNotIn(op, active)
                active[op] = event["timestamp_s"]
            elif (
                event["event_type"] in ("completed", "operator_released", "fault")
                and op is not None
            ):
                busy[op] += event["timestamp_s"] - active.pop(op)
        for op, start in active.items():
            busy[op] += result["production_window_s"] - start
        for op, metrics in enumerate(result["operators"]):
            self.assertAlmostEqual(busy[op], metrics["productive_time_s"])
        for station in result["stations"]:
            self.assertAlmostEqual(
                sum(
                    station[k]
                    for k in [
                        "productive_time_s",
                        "fault_time_s",
                        "blocked_time_s",
                        "starved_time_s",
                        "waiting_for_operator_time_s",
                    ]
                ),
                result["production_window_s"],
            )
        for snap in snaps:
            self.assertEqual(
                snap["released_units"] - snap["accepted_units"],
                sum(snap["queue_lengths"])
                + sum(u is not None for u in snap["station_units"]),
            )
            for state, op in zip(snap["station_states"], snap["station_operators"]):
                if state == "fault":
                    self.assertIsNone(op)
        accepted = [e["unit_id"] for e in events if e["event_type"] == "accepted"]
        self.assertEqual(len(accepted), len(set(accepted)))

    def test_invalid_reliability(self):
        for key, value in [
            ("mtbf_s", 0),
            ("repair_mean_s", -1),
            ("mtbf_s", float("nan")),
            ("uptime_distribution", "unsupported"),
        ]:
            config = self.simple()
            config["stations"][0]["reliability"][key] = value
            with self.assertRaises(ValueError):
                simulate(config)


if __name__ == "__main__":
    unittest.main()
