# EnergyLine S3 — Wokwi controller demonstration

A small Arduino Uno demonstration of the 5 V LED interface. It runs a three-second LED cycle using part, cover and permit inputs, START and RESET buttons, and READY/FAULT indicators. No equipment purchase is needed to use the virtual demonstration.

## Open and run

Open https://wokwi.com/projects/new/arduino-uno. Replace `sketch.ino` and `diagram.json` in the web editor with these local files, then press Play. No external Arduino libraries are required. Saved public project: https://wokwi.com/projects/480261288480719873. The saved project opens stopped with all three switches left; press Play to begin.

All three slide switches start to the left. Right means part present, cover closed, or permit enabled. Leave PART left on startup; a part already present at startup causes a latched BOOT_OCCUPIED fault.

1. Start the simulation with PART absent.
2. Move COVER and PERMIT right. Move PART right to load a part.
3. Press START for at least 25 ms. The clamp-command LED lights for three seconds, then switches off and the serial monitor reports COMPLETE.
4. Move PART left to unload. The controller returns to IDLE. A new cycle requires another START press; holding START never repeats the cycle.
5. During a running cycle, move any slide switch left. The LED turns off and FAULT latches. Restore COVER and PERMIT, remove PART, release START, and press RESET. The output remains off until a new valid cycle is requested.

The saved project starts with PART absent and COVER/PERMIT disabled. Press Play, enable COVER and PERMIT, then load PART and press START.

## Pins and interface mapping

| Uno pin | Signal | Logical meaning | PCB reference |
|---|---|---|---|
| D2 | PART_N | LOW = present | J2 pin 4 |
| D3 | COVER_N | LOW = closed | J2 pin 5 |
| D4 | PERMIT_OK | HIGH = enabled | J2 pin 6 |
| D5 | START | Active-low pushbutton | External controller panel |
| D6 | RESET | Active-low pushbutton | External controller panel |
| D8 | CLAMP_CMD | HIGH = LED command | J2 pin 3 |
| D10 | READY | IDLE with cover and permit enabled | Demo indicator only |
| D11 | FAULT | Latched fault state | Demo indicator only |

PART/COVER use the Uno's internal pull-ups and connect to ground in the right-hand position. The permit SPDT drives D4 to ground or +5 V. The real PCB instead obtains PERMIT_OK from its load rail with a 10 kohm pull-down. START and RESET use INPUT_PULLUP with 25 ms stable-state debouncing. Slide-switch bounce is disabled intentionally; fault input loss is handled directly rather than delayed by button debouncing.

The demo LEDs use 680 ohm series resistors. These indicators are GPIO logic demonstrations: the actual PCB LED is driven through its transistor network. Do not directly wire this simulated indicator circuit into the transistor collector or substitute it for the PCB assembly guide. Use common ground and follow the single-supply instructions in the electrical assembly guide for any later physical build.

## Verification

The corrected sketch compiled and ran in Wokwi on an Arduino Uno. Live serial evidence is in `live_test_log.txt`. Observed cases:

- Initial outputs off with all slide switches left.
- A valid cycle entered RUNNING at 29575 ms and COMPLETE at 32575 ms.
- Permit removal during a later cycle produced PERMIT_REMOVED with command off at 62641 ms.
- Restoring permit and pressing RESET while occupied did not clear the fault.
- Removing the part and pressing RESET returned to IDLE at 74957 ms without enabling the output.
- Cover opening during a cycle produced COVER_OPEN with command off at 81464 ms.
- Part removal during a cycle produced PART_LOST with command off at 96745 ms.

These timestamps belong to the captured simulator run, not measured hardware. The controller's exact source code also passed 26 native C++ assertions via `python3 wokwi/test_controller.py`, including held START/RESET behavior, boot occupancy, the cycle deadline, and unsigned timer rollover. See `controller_test_results.json`. Native tests exercise the controller core; Wokwi separately verifies the compiled Arduino sketch and virtual GPIO wiring.

## Scope

This is a standalone bench firmware demonstration, not a port or replacement of `src/controls/s3_controller.py`. The full virtual-cell controller has additional sequencing, clamp feedback, unit IDs, retained-part recovery, process results, transfer logic and persistent journals. The Arduino demo has none of those. It switches an LED off on fault; it does not claim to release or retain a real clamped part.

There is no n8n, network or telemetry integration in this Wokwi project. It does not simulate the manufactured PCB's transistor currents, fuse behavior or RC networks. Keep using ngspice for those circuit checks. No certified safety function or physical hardware validation is claimed.

References: https://docs.wokwi.com/parts/wokwi-slide-switch and https://docs.wokwi.com/parts/wokwi-pushbutton
