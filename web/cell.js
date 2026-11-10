const $ = (id) => document.getElementById(id);
let result = null,
  index = 0,
  playing = false,
  lastTime = null,
  elapsed = 0,
  demos = [];
const inputNames = [
  "part_present",
  "cover_present",
  "clamp_closed",
  "clamp_open",
  "process_done",
  "downstream_ready",
  "safety_permit",
  "communication_ok",
  "transfer_confirmed",
];
const outputNames = [
  "clamp_command",
  "process_start",
  "process_enable",
  "motion_enable",
  "transfer_request",
  "station_ready",
  "station_fault",
];
const stateNames = [
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
];
async function api(path, body) {
  const response = await fetch(
    path,
    body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : {},
  );
  const value = await response.json();
  if (!response.ok) throw Error(value.error || "Request failed");
  return value;
}
function setupSignals(container, names) {
  for (const name of names) {
    const row = document.createElement("div");
    row.className = "signal";
    row.dataset.name = name;
    const title = document.createElement("span");
    title.textContent = name;
    const value = document.createElement("span");
    const lamp = document.createElement("i");
    lamp.className = "lamp";
    value.append(lamp, document.createTextNode("OFF"));
    row.append(title, value);
    $(container).append(row);
  }
}
setupSignals("inputs", inputNames);
setupSignals("outputs", outputNames);
for (const name of stateNames) {
  const chip = document.createElement("span");
  chip.className = "state-chip";
  chip.textContent = name;
  $("state-sequence").append(chip);
}
function signals(container, values) {
  for (const row of $(container).children) {
    const on = Boolean(values[row.dataset.name]);
    row.classList.toggle("on", on);
    row.lastChild.lastChild.textContent = on ? "ON" : "OFF";
  }
}
function render() {
  if (!result) return;
  const frame = result.timeline[index];
  $("state-badge").textContent = frame.controller_state;
  $("clock").textContent = frame.timestamp_s.toFixed(2) + " s";
  $("scrub").value = index;
  $("module").style.opacity = frame.signals.part_present ? "1" : ".08";
  $("cover").style.opacity = frame.signals.cover_present ? "1" : "0";
  const position = frame.equipment.clamp_position;
  $("left-clamp").setAttribute("transform", `translate(${position * 18},0)`);
  $("right-clamp").setAttribute("transform", `translate(${-position * 18},0)`);
  $("process-light").setAttribute(
    "fill",
    frame.outputs.process_enable
      ? "#d68142"
      : frame.signals.process_done
        ? "#609259"
        : "#aab8a3",
  );
  $("unit-label").textContent = frame.signals.part_present
    ? frame.signals.unit_id
    : "FIXTURE EMPTY";
  signals("inputs", frame.signals);
  signals("outputs", frame.outputs);
  for (const chip of $("state-sequence").children)
    chip.classList.toggle(
      "active",
      chip.textContent === frame.controller_state,
    );
  $("fault-label").hidden = !frame.fault_code;
  $("fault-label").textContent = frame.fault_code
    ? `Fault retained: ${frame.fault_code} · result preserved for reconciliation`
    : "";
  const completed = result.events.filter(
    (e) => e.event_type === "completed" && e.timestamp_s <= frame.timestamp_s,
  ).length;
  $("result-label").textContent =
    `Process result: ${frame.result} · S3 completion records: ${completed} · route: ${frame.outputs.transfer_route}`;
  const log = $("event-log");
  log.replaceChildren();
  const events = [...result.events, ...result.external_actions]
    .filter((e) => e.timestamp_s <= frame.timestamp_s)
    .sort((a, b) => a.timestamp_s - b.timestamp_s);
  for (const event of events) {
    const row = document.createElement("div");
    row.className = "event-row";
    const time = document.createElement("time");
    time.textContent = event.timestamp_s.toFixed(2);
    const text = document.createElement("span");
    text.textContent = `${event.event_type}${event.state ? " · " + event.state : ""}${event.fault_code ? " · " + event.fault_code : ""}${event.route ? " · " + event.route : ""}`;
    row.append(time, text);
    log.append(row);
  }
}
function animate(time) {
  if (playing && result) {
    if (lastTime !== null)
      elapsed += ((time - lastTime) / 1000) * Number($("speed").value);
    index = Math.min(
      result.timeline.length - 1,
      Math.floor(elapsed / result.dt_s),
    );
    render();
    if (index === result.timeline.length - 1) {
      playing = false;
      $("play").textContent = "Replay";
    }
  }
  lastTime = time;
  requestAnimationFrame(animate);
}
requestAnimationFrame(animate);
$("play").onclick = () => {
  if (!result) return;
  if (index === result.timeline.length - 1) {
    elapsed = 0;
    index = 0;
  }
  playing = !playing;
  $("play").textContent = playing ? "Pause" : "Play";
  lastTime = null;
};
$("scrub").oninput = () => {
  index = Number($("scrub").value);
  elapsed = result.timeline[index].timestamp_s;
  playing = false;
  $("play").textContent = "Play";
  render();
};
function note() {
  const demo = demos.find((d) => d.id === $("demo").value);
  $("demo-note").textContent = demo?.expected_fault
    ? `Expected fault: ${demo.expected_fault}. The unit is quarantined during explicit recovery.`
    : "Expected: one S3 completion record, correct routing, and return to IDLE.";
}
$("demo").onchange = note;
$("run-cell").onclick = async () => {
  playing = false;
  $("run-cell").disabled = true;
  $("cell-status").textContent = "Running controller and equipment model…";
  try {
    result = await api("/api/cell/demo", { demo: $("demo").value });
    index = 0;
    elapsed = 0;
    lastTime = null;
    playing = true;
    $("play").disabled = false;
    $("play").textContent = "Pause";
    $("scrub").disabled = false;
    $("scrub").max = result.timeline.length - 1;
    $("cell-status").textContent =
      `Recorded ${result.duration_s.toFixed(2)} simulated seconds. Playing back the trace.`;
    $("checks-summary").textContent =
      `${result.passed ? "PASS" : "FAIL"} · ${Object.values(result.checks).filter(Boolean).length}/${Object.keys(result.checks).length} checks · synthetic equipment inputs`;
    $("checks").replaceChildren();
    for (const [name, passed] of Object.entries(result.checks)) {
      const row = document.createElement("div");
      row.className = "check" + (passed ? "" : " fail");
      row.textContent = `${passed ? "✓" : "×"} ${name.replaceAll("_", " ")}`;
      $("checks").append(row);
    }
    $("trace-link").hidden = false;
    $("trace-link").href = result.artifact;
    render();
  } catch (error) {
    $("cell-status").textContent = error.message;
  } finally {
    $("run-cell").disabled = false;
  }
};
(async () => {
  try {
    demos = await api("/api/cell/demos");
    for (const demo of demos) {
      const option = document.createElement("option");
      option.value = demo.id;
      option.textContent = demo.label;
      $("demo").append(option);
    }
    note();
  } catch (error) {
    $("cell-status").textContent = error.message;
    $("run-cell").disabled = true;
  }
})();
