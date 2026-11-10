import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/simulation"))
from finite_buffers import simulate


class QualityTests(unittest.TestCase):
    def config(self):
        return {
            "model_version": "test",
            "scenario": "quality",
            "input_source": "synthetic",
            "shift_duration_s": 10,
            "planned_nonproduction_s": 0,
            "target_good_units": 1,
            "seed": 1,
            "operator_count": 3,
            "buffer_capacities": [1, 1],
            "stations": [
                {"id": "S1", "mean_process_s": 1},
                {"id": "S4", "mean_process_s": 1},
                {"id": "S5", "mean_process_s": 1},
            ],
            "quality": {
                "inspection_station": "S4",
                "defect_probabilities": {"S1": 1},
                "rework": {"duration_s": 2, "success_probability": 1},
            },
        }

    def invariants(self, config):
        events, result, snaps = simulate(config)
        self.assertEqual(
            result["released_units"],
            result["accepted_units"]
            + result["scrapped_units"]
            + result["unfinished_units"],
        )
        accepted = {e["unit_id"] for e in events if e["event_type"] == "accepted"}
        scrapped = {e["unit_id"] for e in events if e["event_type"] == "scrapped"}
        self.assertFalse(accepted & scrapped)
        self.assertEqual(
            len(accepted), sum(e["event_type"] == "accepted" for e in events)
        )
        for snap in snaps:
            physical = (
                sum(u is not None for u in snap["station_units"])
                + sum(snap["queue_lengths"])
                + snap["rework_queue_length"]
                + int(snap["rework_unit"] is not None)
            )
            self.assertEqual(
                snap["released_units"]
                - snap["accepted_units"]
                - snap["scrapped_units"],
                physical,
            )
            self.assertTrue(
                all(
                    q <= c
                    for q, c in zip(snap["queue_lengths"], config["buffer_capacities"])
                )
            )
        self.assertTrue(all(r["rework_count"] <= 1 for r in result["unit_records"]))
        return events, result, snaps

    def test_rework_success_rejoins_labeling(self):
        events, result, _ = self.invariants(self.config())
        unit = [e for e in events if e["unit_id"] == "UNIT-000001"]
        self.assertEqual(
            next(e["timestamp_s"] for e in unit if e["event_type"] == "accepted"), 5
        )
        self.assertTrue(
            any(
                e["station_id"] == "S5" and e["event_type"] == "completed" for e in unit
            )
        )
        self.assertEqual(result["first_pass_yield"], 0)
        self.assertEqual(result["scrapped_units"], 0)
        self.assertEqual(result["accepted_units"], result["accepted_after_rework"])
        self.assertTrue(
            all(
                r["defect_origins"] == ["S1"]
                for r in result["unit_records"]
                if r["rework_count"]
            )
        )
        self.assertEqual(result["paid_labor_hours"], 4 * 10 / 3600)

    def test_failed_rework_scraps_once(self):
        config = self.config()
        config["quality"]["rework"]["success_probability"] = 0
        events, result, _ = self.invariants(config)
        self.assertEqual(result["accepted_units"], 0)
        self.assertGreater(result["scrapped_units"], 0)
        self.assertTrue(
            all(e["rework_count"] == 1 for e in events if e["event_type"] == "scrapped")
        )

    def test_no_rework_scraps_at_inspection(self):
        config = self.config()
        config["quality"]["rework"] = None
        events, result, _ = self.invariants(config)
        self.assertEqual(result["accepted_units"], 0)
        self.assertEqual(result["rework_started_units"], 0)
        self.assertTrue(
            all(
                e["station_id"] == "S4" for e in events if e["event_type"] == "scrapped"
            )
        )

    def test_zero_defects_matches_reference(self):
        config = self.config()
        config["quality"]["defect_probabilities"] = {}
        _, result, _ = self.invariants(config)
        del config["quality"]
        _, reference, _ = simulate(config)
        for key in [
            "accepted_units",
            "released_units",
            "unfinished_units",
            "time_weighted_mean_wip",
        ]:
            self.assertEqual(result[key], reference[key])
        self.assertEqual(result["first_pass_yield"], 1)

    def test_rework_unfinished_at_cutoff(self):
        config = self.config()
        config["shift_duration_s"] = 3
        _, result, _ = self.invariants(config)
        self.assertEqual(result["accepted_units"], 0)
        self.assertEqual(result["rework_passed_units"], 0)
        self.assertEqual(result["rework_resource"]["processing_time_s"], 1)

    def test_rework_output_blocks_when_final_station_busy(self):
        config = self.config()
        config.update(shift_duration_s=50, buffer_capacities=[0, 0])
        config["stations"][-1]["mean_process_s"] = 8
        _, result, _ = self.invariants(config)
        self.assertGreater(result["rework_resource"]["blocked_time_s"], 0)

    def test_quality_with_failures_and_shared_operators(self):
        config = json.loads(
            (ROOT / "configs/scenarios/D_faster_s2_s3.json").read_text()
        )
        config["quality"] = {
            "inspection_station": "S4",
            "defect_probabilities": {"S2": 0.1, "S3": 0.1},
            "rework": {"duration_s": 180, "success_probability": 0.7},
        }
        for s in config["stations"]:
            if s["id"] in ("S2", "S3"):
                s.update(
                    operator_attended_fraction=0.5,
                    reliability={"mtbf_s": 1800, "repair_mean_s": 180},
                )
        result = self.invariants(config)
        self.assertEqual(result, simulate(config))
        self.assertGreater(result[1]["rework_started_units"], 0)

    def test_trace_reconciles_time_weighted_wip_and_origins(self):
        config = self.config()
        config["quality"]["defect_probabilities"]["S4"] = 1
        events, result, _ = self.invariants(config)
        population = 0
        area = 0
        last = 0
        for event in events:
            area += population * (event["timestamp_s"] - last)
            last = event["timestamp_s"]
            if event["event_type"] == "released":
                population += 1
            if event["event_type"] in ("accepted", "scrapped"):
                population -= 1
        area += population * (config["shift_duration_s"] - last)
        self.assertAlmostEqual(
            result["time_weighted_mean_wip"], area / config["shift_duration_s"]
        )
        self.assertTrue(
            all(
                r["defect_origins"] == ["S1", "S4"]
                for r in result["unit_records"]
                if r["rework_count"]
            )
        )

    def test_no_rework_start_at_shift_boundary(self):
        config = self.config()
        config["shift_duration_s"] = 2
        events, result, _ = self.invariants(config)
        self.assertEqual(result["rework_started_units"], 0)
        self.assertEqual(result["rework_resource"]["queued_at_shift_end"], 1)
        self.assertFalse(
            any(
                e["timestamp_s"] >= 2
                for e in events
                if e["event_type"] == "rework_started"
            )
        )

    def test_invalid_quality(self):
        for p in (-1, 1.1, True, float("nan")):
            config = self.config()
            config["quality"]["defect_probabilities"]["S1"] = p
            with self.assertRaises(ValueError):
                simulate(config)
        config = self.config()
        config["quality"]["inspection_station"] = "S5"
        with self.assertRaises(ValueError):
            simulate(config)


if __name__ == "__main__":
    unittest.main()
