"""S3 controller. Consumes input signals only; never reads equipment internals."""

import copy

STATES = [
    "IDLE",
    "CLAMPING",
    "PROCESSING",
    "CHECK_RESULT",
    "WAIT_TRANSFER",
    "RELEASE",
    "COMPLETE",
    "FAULT",
    "RECOVERY",
    "RECOVERY_RELEASE",
]


class S3Controller:
    def __init__(self, journal=None):
        self.journal = (
            copy.deepcopy(journal)
            if journal is not None
            else {"cycle_number": 0, "units": {}}
        )
        self.state = "IDLE"
        self.since = 0
        self.fault_code = ""
        self.unit = None
        self.result = "pending"
        self.outputs = {
            "clamp_command": False,
            "process_start": False,
            "transfer_request": False,
            "station_ready": True,
            "station_fault": False,
            "transfer_route": "pending",
            "motion_enable": False,
            "process_enable": False,
        }
        self.events = []
        self.boot = True
        self.previous_start = False

    def event(self, now, event_type, **extra):
        self.events.append(
            {
                "timestamp_s": round(now, 4),
                "station_id": "S3",
                "unit_id": self.unit,
                "cycle_number": self.journal["cycle_number"],
                "event_type": event_type,
                "state": self.state,
                "result": self.result,
                "fault_code": self.fault_code,
                **extra,
            }
        )

    def transition(self, now, state):
        self.state = state
        self.since = now
        self.event(now, "state_changed")

    def fault(self, now, code):
        if self.state == "FAULT":
            return
        self.fault_code = code
        self.outputs.update(
            process_start=False,
            process_enable=False,
            motion_enable=False,
            transfer_request=False,
            station_ready=False,
            station_fault=True,
        )
        # Hold existing clamp request. Never automatically release a retained part.
        self.transition(now, "FAULT")
        self.event(now, "fault")

    def output_snapshot(self, inputs):
        self.outputs["station_ready"] = (
            self.state == "IDLE"
            and not inputs["part_present"]
            and inputs["clamp_open"]
            and not inputs["clamp_closed"]
            and inputs["communication_ok"]
            and inputs["safety_permit"]
        )
        return self.outputs.copy()

    def tick(self, now, inputs, commands=None):
        commands = commands or {}
        start = bool(commands.get("start_request"))
        edge = start and not self.previous_start
        self.previous_start = start
        self.outputs["process_start"] = False
        if self.boot:
            self.boot = False
            unresolved = [
                unit
                for unit, record in self.journal["units"].items()
                if record.get("disposition") == "in_process"
            ]
            if unresolved:
                self.unit = unresolved[0]
                self.fault(
                    now,
                    (
                        "RESTART_OCCUPIED"
                        if inputs["part_present"]
                        else "RESTART_UNRESOLVED"
                    ),
                )
            elif inputs["part_present"]:
                self.unit = inputs.get("unit_id")
                self.fault(now, "RESTART_OCCUPIED")
        active = self.state not in ("IDLE", "FAULT", "RECOVERY", "COMPLETE")
        if active and not inputs["communication_ok"]:
            self.fault(now, "COMMUNICATION_LOSS")
        elif active and not inputs["safety_permit"]:
            self.fault(now, "PERMIT_REMOVED")
        if self.state in ("CLAMPING", "PROCESSING", "CHECK_RESULT", "WAIT_TRANSFER"):
            if not inputs["part_present"] or not inputs["cover_present"]:
                self.fault(now, "PART_OR_COVER_LOST")
            elif inputs.get("unit_id") != self.unit:
                self.fault(now, "UNIT_ID_CHANGED")
            elif inputs["clamp_closed"] and inputs["clamp_open"]:
                self.fault(now, "CONTRADICTORY_CLAMP_FEEDBACK")
            elif self.state != "CLAMPING" and not inputs["clamp_closed"]:
                self.fault(now, "CLAMP_CONFIRMATION_LOST")
        if self.state == "FAULT":
            resolved = (
                inputs["communication_ok"]
                and inputs["safety_permit"]
                and not inputs.get("fault_cause_active", False)
            )
            if commands.get("reset_request") and resolved:
                self.outputs["station_fault"] = False
                self.transition(now, "RECOVERY")
                self.event(now, "reset_acknowledged")
            return self.output_snapshot(inputs)
        if self.state == "RECOVERY":
            if (
                commands.get("recover_request")
                and inputs["communication_ok"]
                and inputs["safety_permit"]
            ):
                if (
                    self.unit
                    and self.journal["units"].get(self.unit, {}).get("disposition")
                    != "completed"
                ):
                    self.journal["units"][self.unit] = {
                        "disposition": "quarantined",
                        "result": "uncertain",
                        "cycle_number": self.journal["cycle_number"],
                    }
                    self.event(now, "quarantined")
                self.outputs.update(
                    clamp_command=False, transfer_request=False, motion_enable=True
                )
                self.transition(now, "RECOVERY_RELEASE")
            return self.output_snapshot(inputs)
        if self.state == "RECOVERY_RELEASE":
            if (
                inputs["communication_ok"]
                and inputs["safety_permit"]
                and inputs["clamp_open"]
                and not inputs["part_present"]
            ):
                self.unit = None
                self.result = "pending"
                self.fault_code = ""
                self.transition(now, "IDLE")
                self.outputs.update(station_ready=True, motion_enable=False)
            return self.output_snapshot(inputs)
        if self.state == "IDLE" and edge:
            self.unit = inputs.get("unit_id")
            self.result = "pending"
            if not inputs["part_present"]:
                self.fault(now, "MISSING_TRAY")
            elif not inputs["cover_present"]:
                self.fault(now, "MISSING_COVER")
            elif not self.unit:
                self.fault(now, "MISSING_UNIT_ID")
            elif self.unit in self.journal["units"]:
                self.fault(now, "DUPLICATE_UNIT_ID")
            elif not inputs["clamp_open"] or inputs["clamp_closed"]:
                self.fault(now, "FIXTURE_NOT_OPEN")
            elif inputs["process_done"] or inputs["process_pass"] is not None:
                self.fault(now, "STALE_PROCESS_RESULT")
            elif not inputs["communication_ok"]:
                self.fault(now, "COMMUNICATION_LOSS")
            elif not inputs["safety_permit"]:
                self.fault(now, "PERMIT_REMOVED")
            else:
                self.journal["cycle_number"] += 1
                self.journal["units"][self.unit] = {
                    "disposition": "in_process",
                    "result": "pending",
                    "cycle_number": self.journal["cycle_number"],
                }
                self.outputs.update(
                    clamp_command=True,
                    station_ready=False,
                    transfer_route="pending",
                    motion_enable=True,
                )
                self.transition(now, "CLAMPING")
        elif self.state == "CLAMPING":
            if inputs["clamp_closed"]:
                self.outputs["process_start"] = True
                self.outputs["process_enable"] = True
                self.transition(now, "PROCESSING")
                self.event(now, "process_command")
            elif now - self.since >= 1.5:
                self.fault(now, "CLAMP_TIMEOUT")
        elif self.state == "PROCESSING":
            if inputs["process_done"]:
                self.outputs["process_enable"] = False
                self.transition(now, "CHECK_RESULT")
            elif now - self.since >= 4:
                self.fault(now, "PROCESS_TIMEOUT")
        elif self.state == "CHECK_RESULT":
            if type(inputs["process_pass"]) is not bool:
                self.fault(now, "INVALID_PROCESS_RESULT")
            else:
                self.result = "pass" if inputs["process_pass"] else "fail"
                self.journal["units"][self.unit]["result"] = self.result
                self.outputs["transfer_route"] = (
                    "accepted" if self.result == "pass" else "rework"
                )
                self.event(now, "result_latched")
                self.transition(now, "WAIT_TRANSFER")
        elif self.state == "WAIT_TRANSFER":
            if inputs["downstream_ready"]:
                self.outputs.update(clamp_command=False, transfer_request=True)
                self.transition(now, "RELEASE")
        elif self.state == "RELEASE":
            if (
                inputs["transfer_confirmed"]
                and not inputs["part_present"]
                and inputs["clamp_open"]
            ):
                self.outputs["transfer_request"] = False
                self.transition(now, "COMPLETE")
            elif now - self.since >= 2:
                self.fault(now, "TRANSFER_TIMEOUT")
        elif self.state == "COMPLETE":
            record = self.journal["units"][self.unit]
            if record["disposition"] != "completed":
                record.update(
                    disposition="completed",
                    result=self.result,
                    route=self.outputs["transfer_route"],
                )
                self.event(now, "completed", route=self.outputs["transfer_route"])
            self.unit = None
            self.result = "pending"
            self.outputs.update(
                station_ready=True, motion_enable=False, process_enable=False
            )
            self.transition(now, "IDLE")
        return self.output_snapshot(inputs)
