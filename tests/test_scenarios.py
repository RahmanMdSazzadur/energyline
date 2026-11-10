import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/simulation"))
from finite_buffers import simulate


class ScenarioTests(unittest.TestCase):
    def load(self, name):
        return json.loads((ROOT / f"configs/scenarios/{name}.json").read_text())

    def test_controlled_changes(self):
        baseline = self.load("A_manual")
        for name, changes in [
            ("B_fixture_s3", {"S3": 110}),
            ("C_faster_s3", {"S3": 70}),
            ("D_faster_s2_s3", {"S2": 65, "S3": 70}),
        ]:
            case = self.load(name)
            for key in [
                "buffer_capacities",
                "processing_time",
                "seed",
                "shift_duration_s",
                "operator_count",
            ]:
                self.assertEqual(case[key], baseline[key])
            for old, new in zip(baseline["stations"], case["stations"]):
                self.assertEqual(
                    new["mean_process_s"], changes.get(old["id"], old["mean_process_s"])
                )

    def test_dedicated_resource_analytical_completion_counts(self):
        for name, first, interval in [
            ("A_manual", 465, 150),
            ("B_fixture_s3", 425, 120),
            ("C_faster_s3", 385, 120),
            ("D_faster_s2_s3", 330, 90),
        ]:
            config = self.load(name)
            config.update(operator_count=5, processing_time={"distribution": "fixed"})
            events, result, _ = simulate(config)
            expected = list(range(first, 25201, interval))
            self.assertEqual(
                [e["timestamp_s"] for e in events if e["event_type"] == "accepted"],
                expected,
            )
            self.assertEqual(result["accepted_units"], len(expected))

    def test_target_does_not_change_physical_output(self):
        config = self.load("D_faster_s2_s3")
        events, result, snapshots = simulate(config)
        for target in (160, 320):
            case = copy.deepcopy(config)
            case["target_good_units"] = target
            other_events, other_result, other_snapshots = simulate(case)
            self.assertEqual(events, other_events)
            self.assertEqual(snapshots, other_snapshots)
            self.assertEqual(result["accepted_units"], other_result["accepted_units"])
            self.assertEqual(
                other_result["demand_met"], result["accepted_units"] >= target
            )


if __name__ == "__main__":
    unittest.main()
