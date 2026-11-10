"""Independent inert equipment model; consumes commands, produces sensor feedback."""


class S3Equipment:
    def __init__(self):
        self.unit_id = None
        self.part_present = False
        self.cover_present = False
        self.clamp_position = 0.0
        self.process_elapsed = 0.0
        self.process_running = False
        self.process_done = False
        self.process_pass = None
        self.transfer_elapsed = 0.0
        self.transfer_confirmed = False
        self.downstream_ready = True
        self.safety_permit = True
        self.communication_ok = True
        self.clamp_jammed = False
        self.process_jammed = False
        self.force_process_fail = False
        self.process_starts = 0
        self.transfers = []
        self.previous_process_start = False

    def load(self, unit_id, cover=True, tray=True):
        if self.part_present or self.clamp_position > 0:
            raise ValueError("Fixture must be empty and open before loading")
        self.unit_id = unit_id
        self.part_present = tray
        self.cover_present = cover
        self.process_elapsed = 0
        self.process_running = False
        self.process_done = False
        self.process_pass = None
        self.transfer_elapsed = 0
        self.transfer_confirmed = False

    def remove(self):
        if self.clamp_position > 0:
            raise ValueError("Open the clamp before manual removal")
        self.part_present = False
        self.cover_present = False
        self.unit_id = None
        self.process_running = False

    def signals(self):
        return {
            "unit_id": self.unit_id,
            "part_present": self.part_present,
            "cover_present": self.cover_present,
            "clamp_closed": self.clamp_position >= 1,
            "clamp_open": self.clamp_position <= 0,
            "process_done": self.process_done,
            "process_pass": self.process_pass,
            "downstream_ready": self.downstream_ready,
            "safety_permit": self.safety_permit,
            "communication_ok": self.communication_ok,
            "transfer_confirmed": self.transfer_confirmed,
            "fault_cause_active": self.clamp_jammed or self.process_jammed,
        }

    def step(self, dt, outputs):
        rising = outputs["process_start"] and not self.previous_process_start
        self.previous_process_start = outputs["process_start"]
        if not self.communication_ok or not self.safety_permit:
            return
        if not self.clamp_jammed and outputs["motion_enable"]:
            direction = 1 if outputs["clamp_command"] else -1
            self.clamp_position = max(
                0, min(1, self.clamp_position + direction * dt / 0.6)
            )
        if (
            rising
            and self.part_present
            and self.cover_present
            and self.clamp_position >= 1
            and not self.process_done
        ):
            self.process_running = True
            self.process_starts += 1
        if (
            self.process_running
            and not self.process_jammed
            and outputs["process_enable"]
        ):
            self.process_elapsed += dt
            if self.process_elapsed >= 2:
                self.process_running = False
                self.process_done = True
                self.process_pass = not self.force_process_fail
        if (
            outputs["motion_enable"]
            and outputs["transfer_request"]
            and self.downstream_ready
            and self.clamp_position <= 0
            and self.part_present
        ):
            self.transfer_elapsed += dt
            if self.transfer_elapsed >= 0.7:
                self.transfers.append(
                    {"unit_id": self.unit_id, "route": outputs["transfer_route"]}
                )
                self.part_present = False
                self.cover_present = False
                self.unit_id = None
                self.transfer_confirmed = True
