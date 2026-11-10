# Virtual S3 cell — v0.2.0

## Open and run

Open http://localhost:8787/cell. Select a commissioning scenario and click **Run demonstration**. The backend executes a deterministic software-in-the-loop test; the browser then plays back its recorded signal trace. Pause, replay or scrub to inspect individual states. Scenario injection, reset, explicit recovery and operator removal are scripted, not live user commands. The evidence panel covers the full trace even while playback is paused earlier in that trace.

The equipment view shows tray/cover presence, clamp position, a mock-fastening indicator, controller state, sensor inputs and command outputs. **Open recorded trace** retrieves that run's saved JSON from the local service. The experiment studio links to the cell.

## Independent models

- `src/controls/s3_controller.py`: controller state machine and production journal; consumes signal dictionaries only.
- `src/equipment_model/s3_equipment.py`: equipment dynamics and sensor feedback; consumes output commands only and does not read controller state.
- `src/cell/s3_demo.py`: commissioning harness, operator actions, faults, recorded I/O and assertions.

The harness advances in 0.05-second steps. Illustrative equipment timings are 0.6 seconds to move a clamp, 2 seconds of mock processing, and 0.7 seconds to transfer after opening. Controller timeouts are 1.5 seconds for clamp confirmation, 4 seconds for process completion and 2 seconds for transfer. These accelerated teaching values do not justify the separate 70-second production scenario estimate.

## Normal sequence

IDLE → CLAMPING → PROCESSING → CHECK_RESULT → WAIT_TRANSFER → RELEASE → COMPLETE → IDLE.

Start requires a tray, cover, unit ID, communications and permit. Repeated held start does not start additional cycles. The controller pulses process_start once, latches pass/fail, and retains the result while waiting downstream. Transfer is modeled only after the clamp opens. Completion requires transfer confirmation, part absence and an open clamp. A passing S3 result routes to accepted; a failed result routes to rework. S3 completion is a cell record, not final good-line output at S5.

## Fault and recovery

Fault removes process_enable, motion_enable, process_start and transfer_request, disables ready and sets station_fault. It holds the existing clamp position request. The equipment pauses its process and physical motion when these enables are removed. Returning communications, permit or jam clearance does not automatically resume work.

Once the reported fault cause clears, reset acknowledges it and enters RECOVERY with motion still disabled. A separate recover_request quarantines the uncertain unit and explicitly permits clamp opening. After the operator removes the unit with an open fixture, the controller returns to IDLE. It does not assign a guessed pass result or emit a production completion for a quarantined unit. Fault codes remain visible until recovery finishes.

The software journal retains cycle number and unit dispositions. Completed or quarantined IDs cannot start again. The restart demonstration serializes and reconstructs the journal, detects an occupied fixture on boot and requires reconciliation. This is simulated restart persistence, not a test of filesystem transactions, power loss or hardware retention.

## Commissioning evidence

Run `python3 src/cell/s3_demo.py` to regenerate `results/s3_commissioning/commissioning.csv`, eleven complete trace JSON files and a source-hash manifest. All eleven cases pass:

1. Normal cycle.
2. Missing tray at start.
3. Missing cover at start.
4. Clamp confirmation timeout.
5. Process timeout.
6. Failed process result routed to rework.
7. Downstream unavailable; completed result retained until permission returns.
8. Permit removed during processing.
9. Communication interruption.
10. Restart with a unit in the fixture.
11. Repeated start request and latched process-done signal.

Each trace includes external actions, I/O samples, equipment variables, state events, fault codes, journal, transfer disposition and check results. Checks cover expected fault, exactly-once completion, final IDLE, one process command, inhibited fault outputs, no motion restart on reset, failed-result routing and retained downstream results. Inapplicable conditional checks pass by definition; the unit test suite adds independent timing and journal assertions.

`docs/io_list.csv` lists implemented signals. Full repository tests: `python3 -m unittest discover -s tests -q`. The release test suite covers cell API save/retrieve/validation and the earlier flow-model regressions.

## Current boundary

This is a software commissioning demonstration with inert virtual equipment and a simulated permit. It is not a certified safety implementation, an actual fastening system, a validated industrial timing study or hardware-in-the-loop test. CAD tolerances, fixture manufacture, real communication protocols and durable power-loss recovery are not demonstrated. The standalone demonstration remains independent. Production experiments can now select `integrated_s3`: a per-unit adapter executes the controller/equipment cycle with the flow ID, maps duration by an explicit assumed scale and routes pass/fail/quarantine into the line. It resets the cell per cycle and is not a continuously connected PLC. n8n can select this scenario through its experiment inputs.

## Run the full suite from n8n

Open your existing n8n workflow list and choose **EnergyLine — commission virtual S3 cell**. It runs all eleven cases and returns a persisted report with an evidence link per case. Source hashes are recorded in that report. n8n routes a false aggregate result to an error node. This is software test orchestration, not a motion-control interface.

The live workflow passed all eleven cases and all persisted trace links were retrieved. The repository includes direct controller and integration regression tests. Repeat requests reuse the same commissioning report; changed source with the same request ID is rejected. Reports are saved through the local service under the existing project results directory and SQLite index.
