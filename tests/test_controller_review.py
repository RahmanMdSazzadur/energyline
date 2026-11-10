import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src/controls"), str(ROOT / "src/equipment_model")]
from s3_controller import S3Controller
from s3_equipment import S3Equipment


class ControllerReviewTests(unittest.TestCase):
    def processing(self):
        controller = S3Controller()
        plant = S3Equipment()
        controller.tick(0, plant.signals())
        plant.load("review-unit")
        controller.tick(0.1, plant.signals(), {"start_request": True})
        plant.clamp_position = 1
        controller.tick(0.8, plant.signals())
        self.assertEqual(controller.state, "PROCESSING")
        return controller, plant

    def test_permit_loss_during_recovery_inhibits_outputs(self):
        controller, plant = self.processing()
        plant.safety_permit = False
        controller.tick(0.9, plant.signals())
        plant.safety_permit = True
        controller.tick(1, plant.signals(), {"reset_request": True})
        controller.tick(1.1, plant.signals(), {"recover_request": True})
        self.assertEqual(controller.state, "RECOVERY_RELEASE")
        plant.safety_permit = False
        outputs = controller.tick(1.2, plant.signals())
        self.assertEqual(controller.state, "FAULT")
        self.assertFalse(outputs["motion_enable"])
        plant.safety_permit = True
        self.assertFalse(controller.tick(1.3, plant.signals())["motion_enable"])

    def test_part_and_cover_loss_stop_processing(self):
        for field in ("part_present", "cover_present"):
            controller, plant = self.processing()
            setattr(plant, field, False)
            outputs = controller.tick(0.9, plant.signals())
            self.assertEqual(controller.fault_code, "PART_OR_COVER_LOST")
            self.assertFalse(outputs["process_enable"])

    def test_changed_unit_id_cannot_complete(self):
        controller, plant = self.processing()
        plant.unit_id = "unexpected-id"
        outputs = controller.tick(0.9, plant.signals())
        self.assertEqual(controller.fault_code, "UNIT_ID_CHANGED")
        self.assertFalse(outputs["process_enable"])
        self.assertFalse(any(e["event_type"] == "completed" for e in controller.events))

    def test_clamp_feedback_loss_and_contradiction(self):
        for contradiction in (False, True):
            controller, plant = self.processing()
            signals = plant.signals()
            signals.update(clamp_closed=contradiction, clamp_open=True)
            controller.tick(0.9, signals)
            self.assertEqual(controller.state, "FAULT")
            self.assertFalse(controller.outputs["process_enable"])

    def test_stale_process_result_blocks_start(self):
        controller = S3Controller()
        plant = S3Equipment()
        controller.tick(0, plant.signals())
        plant.load("review-unit")
        plant.process_done = True
        plant.process_pass = True
        controller.tick(0.1, plant.signals(), {"start_request": True})
        self.assertEqual(controller.fault_code, "STALE_PROCESS_RESULT")
        self.assertFalse(controller.outputs["motion_enable"])

    def test_restart_with_unresolved_absent_unit_requires_reconciliation(self):
        journal = {
            "cycle_number": 1,
            "units": {
                "lost-unit": {
                    "disposition": "in_process",
                    "result": "pending",
                    "cycle_number": 1,
                }
            },
        }
        controller = S3Controller(journal)
        plant = S3Equipment()
        controller.tick(0, plant.signals())
        self.assertEqual(controller.fault_code, "RESTART_UNRESOLVED")
        controller.tick(0.1, plant.signals(), {"reset_request": True})
        controller.tick(0.2, plant.signals(), {"recover_request": True})
        self.assertEqual(
            controller.journal["units"]["lost-unit"]["disposition"], "quarantined"
        )

    def test_ready_requires_open_empty_fixture_and_permit(self):
        controller = S3Controller()
        plant = S3Equipment()
        plant.safety_permit = False
        self.assertFalse(controller.tick(0, plant.signals())["station_ready"])
        plant.safety_permit = True
        self.assertTrue(controller.tick(0.1, plant.signals())["station_ready"])
        plant.load("unit")
        self.assertFalse(controller.tick(0.2, plant.signals())["station_ready"])


if __name__ == "__main__":
    unittest.main()
