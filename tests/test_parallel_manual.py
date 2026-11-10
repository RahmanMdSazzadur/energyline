import copy, json, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/simulation"))
from parallel_manual import simulate
from finite_buffers import simulate as reference


class ParallelTests(unittest.TestCase):
    def config(self):
        c = json.loads((ROOT / "configs/quality_baseline.json").read_text())
        c["operator_count"] = 4
        for s in c["stations"]:
            s.pop("reliability", None)
            s.pop("operator_attended_fraction", None)
            if s["id"] == "S2":
                s["mean_process_s"] = 120
            if s["id"] == "S3":
                s["mean_process_s"] = 150
        return c

    def test_single_server_agrees_with_existing_reference(self):
        for seed in (1, 2, 3):
            c = self.config()
            c["seed"] = seed
            _, a, _ = simulate(c)
            _, b, _ = reference(c)
            for key in [
                "released_units",
                "accepted_units",
                "scrapped_units",
                "unfinished_units",
                "rework_started_units",
            ]:
                self.assertEqual(a[key], b[key])
            self.assertAlmostEqual(
                a["time_weighted_mean_wip"], b["time_weighted_mean_wip"]
            )

    def test_parallel_resources_and_mass_balance(self):
        c = self.config()
        c["parallel_servers"] = [1, 1, 2, 1, 1]
        events, result, snapshots = simulate(c)
        self.assertGreater(result["accepted_units"], 180)
        active = {}
        for e in events:
            if e["station_id"] == "REWORK":
                continue
            op = e["operator_id"]
            if e["event_type"] == "started":
                self.assertNotIn(op, active)
                active[op] = e["unit_id"]
            elif e["event_type"] == "completed":
                self.assertEqual(active.pop(op), e["unit_id"])
        self.assertTrue(
            any(
                e["resource_id"] == "S3-2" and e["event_type"] == "started"
                for e in events
            )
        )
        for s in snapshots:
            physical = (
                sum(u is not None for u in s["station_units"])
                + sum(s["queue_lengths"])
                + s["rework_queue_length"]
                + int(s["rework_unit"] is not None)
            )
            self.assertEqual(
                s["released_units"] - s["accepted_units"] - s["scrapped_units"],
                physical,
            )
            self.assertTrue(all(q <= 2 for q in s["queue_lengths"]))
        ids = [e["unit_id"] for e in events if e["event_type"] == "accepted"]
        self.assertEqual(len(ids), len(set(ids)))

    def test_zero_buffers_and_exact_analytical_bottleneck(self):
        c = self.config()
        c.pop("quality")
        c["processing_time"] = {"distribution": "fixed"}
        c["operator_count"] = 6
        c["parallel_servers"] = [1, 1, 2, 1, 1]
        c["buffer_capacities"] = [0] * 4
        events, result, _ = simulate(c)
        self.assertEqual(result["accepted_units"], 207)
        self.assertEqual(result["first_completion_s"], 465)
        self.assertTrue(all(e["timestamp_s"] <= 25200 for e in events))

    def test_unsupported_automation_rejected(self):
        c = self.config()
        c["stations"][2]["operator_attended_fraction"] = 0.5
        with self.assertRaises(ValueError):
            simulate(c)


if __name__ == "__main__":
    unittest.main()
