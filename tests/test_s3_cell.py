import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/cell"))
from s3_demo import run_demo, DEMOS
from s3_controller import S3Controller
from s3_equipment import S3Equipment


class S3CellTests(unittest.TestCase):
    def test_all_commissioning_demonstrations(self):
        for demo in DEMOS:
            with self.subTest(demo=demo):
                result = run_demo(demo)
                self.assertTrue(result["passed"], result["checks"])
                self.assertEqual(result, run_demo(demo))

    def test_controller_runs_against_signals_without_equipment(self):
        controller = S3Controller()
        inputs = S3Equipment().signals()
        controller.tick(0, inputs)
        inputs.update(part_present=True, cover_present=True, unit_id="test-unit")
        self.assertTrue(
            controller.tick(0.1, inputs, {"start_request": True})["clamp_command"]
        )
        inputs.update(clamp_closed=True, clamp_open=False)
        self.assertTrue(controller.tick(0.8, inputs)["process_start"])
        self.assertFalse(controller.tick(0.85, inputs)["process_start"])
        inputs.update(process_done=True, process_pass=True)
        controller.tick(2.9, inputs)
        controller.tick(3, inputs)
        self.assertEqual(controller.state, "WAIT_TRANSFER")
        self.assertEqual(controller.result, "pass")

    def test_fault_resolution_and_reset_never_resume_motion(self):
        result = run_demo("clamp_timeout")
        for frame in result["timeline"]:
            if frame["controller_state"] in ("FAULT", "RECOVERY"):
                self.assertFalse(frame["outputs"]["motion_enable"])
                self.assertFalse(frame["outputs"]["process_enable"])
                self.assertEqual(frame["equipment"]["clamp_position"], 0)
        self.assertEqual(
            result["journal"]["units"]["S3-DEMO-0001"]["disposition"], "quarantined"
        )

    def test_plant_has_no_autonomous_motion_after_permit_restored(self):
        result = run_demo("permit_removed")
        held = [
            t
            for t in result["timeline"]
            if t["controller_state"] in ("FAULT", "RECOVERY")
        ]
        self.assertEqual(len({t["equipment"]["process_fraction"] for t in held}), 1)
        self.assertEqual(len({t["equipment"]["clamp_position"] for t in held}), 1)

    def test_failed_unit_is_never_marked_good(self):
        result = run_demo("failed_process")
        complete = [e for e in result["events"] if e["event_type"] == "completed"]
        self.assertEqual(len(complete), 1)
        self.assertEqual(complete[0]["result"], "fail")
        self.assertEqual(complete[0]["route"], "rework")

    def test_result_retained_while_downstream_blocked(self):
        result = run_demo("downstream_blocked")
        waiting = [
            t for t in result["timeline"] if t["controller_state"] == "WAIT_TRANSFER"
        ]
        self.assertGreater(len(waiting), 20)
        self.assertTrue(
            all(
                t["result"] == "pass" and not t["outputs"]["transfer_request"]
                for t in waiting
            )
        )
        self.assertTrue(
            all(
                e["timestamp_s"] >= 6
                for e in result["events"]
                if e["event_type"] == "completed"
            )
        )

    def test_occupied_restart_preserves_serialized_journal(self):
        result = run_demo("restart_occupied")
        self.assertTrue(
            any(
                e["event_type"] == "controller_restarted_from_serialized_journal"
                for e in result["external_actions"]
            )
        )
        self.assertEqual(result["journal"]["cycle_number"], 1)
        self.assertFalse(any(e["event_type"] == "completed" for e in result["events"]))
        self.assertEqual(
            result["journal"]["units"]["S3-DEMO-0001"]["disposition"], "quarantined"
        )

    def test_duplicate_unit_id_rejected_without_overwriting_completion(self):
        journal = run_demo("normal")["journal"]
        controller = S3Controller(json.loads(json.dumps(journal)))
        plant = S3Equipment()
        controller.tick(0, plant.signals())
        plant.load("S3-DEMO-0001")
        controller.tick(0.1, plant.signals(), {"start_request": True})
        self.assertEqual(controller.fault_code, "DUPLICATE_UNIT_ID")
        controller.tick(0.2, plant.signals(), {"reset_request": True})
        controller.tick(0.3, plant.signals(), {"recover_request": True})
        self.assertEqual(
            controller.journal["units"]["S3-DEMO-0001"]["disposition"], "completed"
        )
        self.assertFalse(any(e["event_type"] == "completed" for e in controller.events))

    def test_unresolved_fault_cannot_reset(self):
        controller = S3Controller()
        plant = S3Equipment()
        controller.tick(0, plant.signals())
        plant.load("test")
        plant.communication_ok = False
        controller.tick(0.1, plant.signals(), {"start_request": True})
        controller.tick(
            0.2, plant.signals(), {"reset_request": True, "start_request": True}
        )
        self.assertEqual(controller.state, "FAULT")
        self.assertFalse(controller.outputs["motion_enable"])

    def test_equipment_load_and_removal_interlocks(self):
        plant = S3Equipment()
        plant.load("one")
        with self.assertRaises(ValueError):
            plant.load("two")
        plant.clamp_position = 1
        with self.assertRaises(ValueError):
            plant.remove()


if __name__ == "__main__":
    unittest.main()
