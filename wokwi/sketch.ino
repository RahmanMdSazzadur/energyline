#include <Arduino.h>

// S3 bench demonstration. Not a port of the production cell controller.
// No actuator, clamp feedback, unit journal, networking or certified safety.
enum State { IDLE, RUNNING, COMPLETE, FAULT };
struct Inputs { bool part, cover, permit, start, reset; };
struct Controller {
  State state = IDLE;
  bool command = false;
  bool previousStart = false;
  bool previousReset = false;
  bool boot = true;
  uint32_t began = 0;
  const char *reason = "ready";

  void update(uint32_t now, const Inputs &in) {
    const bool startEdge = in.start && !previousStart;
    const bool resetEdge = in.reset && !previousReset;
    previousStart = in.start;
    previousReset = in.reset;
    if (boot) {
      boot = false;
      previousStart = in.start;
      previousReset = in.reset;
      command = false;
      if (in.part) { state = FAULT; reason = "BOOT_OCCUPIED"; }
      return;
    }
    if (state == RUNNING && (!in.permit || !in.cover || !in.part)) {
      state = FAULT;
      reason = !in.permit ? "PERMIT_REMOVED" : !in.cover ? "COVER_OPEN" : "PART_LOST";
    }
    command = false;
    if (state == FAULT) {
      // Remove the part, restore permissives, release START, then press RESET.
      if (resetEdge && in.permit && in.cover && !in.part && !in.start) {
        state = IDLE; reason = "fault reset; load a new part";
      }
      return;
    }
    if (state == COMPLETE) {
      if (!in.part && !in.start) { state = IDLE; reason = "ready"; }
      return;
    }
    if (state == IDLE && startEdge) {
      if (in.part && in.cover && in.permit && !in.reset) {
        state = RUNNING; began = now; reason = "3 second LED cycle";
      } else {
        reason = "START_REJECTED: check part, cover, permit and RESET";
      }
    }
    if (state == RUNNING) {
      if (uint32_t(now - began) >= 3000) {
        state = COMPLETE; reason = "complete; remove part";
      } else { command = true; }
    }
  }
};

// Arduino adapter. PCB J2: 3=CMD, 4=PART_N, 5=COVER_N, 6=PERMIT_OK.
const uint8_t PART_PIN=2, COVER_PIN=3, PERMIT_PIN=4;
const uint8_t START_PIN=5, RESET_PIN=6, CLAMP_PIN=8;
const uint8_t READY_PIN=10, FAULT_PIN=11;
const uint32_t BUTTON_DEBOUNCE_MS=25;
struct Button {
  explicit Button(uint8_t p) : pin(p) {}
  uint8_t pin;
  bool raw=false, stable=false;
  uint32_t changed=0;
  bool read(uint32_t now) {
    bool value=digitalRead(pin)==LOW;
    if (value!=raw) {raw=value; changed=now;}
    if (uint32_t(now-changed)>=BUTTON_DEBOUNCE_MS) stable=raw;
    return stable;
  }
};
Controller cell;
Button startButton{START_PIN}, resetButton{RESET_PIN};
const char *names[]={"IDLE","RUNNING","COMPLETE","FAULT"};
State lastState=FAULT;
const char *lastReason=nullptr;
uint32_t lastStatus=0;
void setup() {
  digitalWrite(CLAMP_PIN,LOW); pinMode(CLAMP_PIN,OUTPUT);
  pinMode(READY_PIN,OUTPUT); pinMode(FAULT_PIN,OUTPUT);
  pinMode(PART_PIN,INPUT_PULLUP); pinMode(COVER_PIN,INPUT_PULLUP);
  pinMode(PERMIT_PIN,INPUT);  // Wokwi SPDT drives both 0V and 5V.
  pinMode(START_PIN,INPUT_PULLUP); pinMode(RESET_PIN,INPUT_PULLUP);
  Serial.begin(115200);
  Serial.println(F("S3 LED BENCH DEMO | no physical actuator"));
  Serial.println(F("Set PART/COVER/PERMIT right, press START. Open any switch during RUNNING to fault."));
  Serial.println(F("Fault reset: remove PART, restore COVER/PERMIT, release START, press RESET."));
}
void loop() {
  uint32_t now=millis();
  Inputs in{digitalRead(PART_PIN)==LOW, digitalRead(COVER_PIN)==LOW,
            digitalRead(PERMIT_PIN)==HIGH,startButton.read(now),resetButton.read(now)};
  cell.update(now,in);
  // Raw permissives gate the output on every loop, without button debounce delay.
  bool enabled=cell.command && in.permit && in.cover && in.part;
  digitalWrite(CLAMP_PIN,enabled?HIGH:LOW);
  digitalWrite(READY_PIN,cell.state==IDLE && in.permit && in.cover?HIGH:LOW);
  digitalWrite(FAULT_PIN,cell.state==FAULT?HIGH:LOW);
  if (cell.state!=lastState || cell.reason!=lastReason || uint32_t(now-lastStatus)>=1000) {
    Serial.print(now); Serial.print(F(" ms | ")); Serial.print(names[cell.state]);
    Serial.print(F(" | PART="));Serial.print(in.part);
    Serial.print(F(" COVER="));Serial.print(in.cover);
    Serial.print(F(" PERMIT="));Serial.print(in.permit);
    Serial.print(F(" CMD="));Serial.print(enabled);
    Serial.print(F(" | "));Serial.println(cell.reason);
    lastState=cell.state;lastReason=cell.reason;lastStatus=now;
  }
  delay(1);
}
