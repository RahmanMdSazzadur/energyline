const el = (id) => document.getElementById(id);
const labels = {};
const fmt = (n, d = 1) => Number(n).toFixed(d);
async function api(path, options) {
  const response = await fetch(path, options);
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || "Request failed");
  return value;
}
function text(id, value) {
  el(id).textContent = value;
}
function render(result) {
  const a = result.aggregate,
    p = result.parameters;
  el("empty").hidden = true;
  el("report").hidden = false;
  text(
    "run-description",
    `${labels[p.scenario] || p.scenario} · ${p.operators} production operators · ${p.replications} shifts · target ${p.target} · seed ${p.seed}`,
  );
  text("mean", fmt(a.mean_good_units));
  text("range", `Observed range ${a.minimum}–${a.maximum} good units`);
  text("attainment", `${a.successful_shifts}/${a.replications}`);
  text(
    "interval",
    `95% attainment interval: ${fmt(a.wilson_95_lower * 100)}–${fmt(a.wilson_95_upper * 100)}%`,
  );
  text("labor", fmt(a.mean_labor_productivity, 2));
  text("scrap", fmt(a.mean_scrapped_units));
  text("unfinished", fmt(a.mean_unfinished_units));
  const bars = el("distribution");
  bars.replaceChildren();
  const max = Math.max(
    p.target,
    ...result.runs.map((r) => r.accepted_units),
    1,
  );
  result.runs.forEach((run, i) => {
    const bar = document.createElement("div");
    bar.className = "bar" + (run.accepted_units >= p.target ? " pass" : "");
    bar.style.height = `${(run.accepted_units / max) * 100}%`;
    bar.title = `Shift ${i + 1}: ${run.accepted_units} good units; target ${p.target}`;
    bars.append(bar);
  });
  const stations = el("stations");
  stations.replaceChildren();
  const categories = [
    ["productive_time_s", "#54755c", "Processing"],
    ["blocked_time_s", "#c7a071", "Blocked"],
    ["fault_time_s", "#bb6456", "Fault"],
    ["waiting_for_operator_time_s", "#8d83ab", "Operator wait"],
    ["starved_time_s", "#d5dece", "Starved"],
  ];
  result.representative_run.stations.forEach((station) => {
    const row = document.createElement("div");
    row.className = "station";
    const name = document.createElement("span");
    name.textContent = station.station_id;
    row.append(name);
    const track = document.createElement("div");
    track.className = "track";
    categories.forEach(([key, color, label]) => {
      const part = document.createElement("i");
      const fraction =
        station[key] / result.representative_run.production_window_s;
      part.style.width = `${fraction * 100}%`;
      part.style.background = color;
      part.title = `${label}: ${fmt(fraction * 100)}%`;
      track.append(part);
    });
    row.append(track);
    stations.append(row);
  });
  el("json").href = result.artifacts.result;
  el("events").href = result.artifacts.first_run_events;
  el("events").download = `${result.id}-first-shift.csv`;
}
async function history() {
  const records = await api("/api/experiments");
  const list = el("history");
  list.replaceChildren();
  if (!records.length) {
    const p = document.createElement("p");
    p.className = "hint";
    p.textContent = "No experiments yet.";
    list.append(p);
    return;
  }
  records.slice(0, 8).forEach((record) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = `${labels[record.scenario] || record.scenario} · ${fmt(record.aggregate.mean_good_units)} good units`;
    const note = document.createElement("span");
    note.textContent = `${record.parameters.operators} operators · ${record.parameters.replications} shifts · ${new Date(record.created_at).toLocaleString()}`;
    button.append(note);
    button.onclick = async () => {
      try {
        render(await api(`/api/experiments/${record.id}`));
      } catch (error) {
        text("status", error.message);
      }
    };
    list.append(button);
  });
}
function scenarioNote() {
  const notes = {
    quality_rework:
      "Includes moderate S2/S3 failures, 50% attended cycles, defects and one extra dedicated rework operator.",
    parallel_s3:
      "Two real manual S3 resource slots, finite buffers and shared production staff; defects and one extra rework operator. Idle station time combines input and operator waits.",
    integrated_s3:
      "Executes the S3 controller/equipment cycle for each unit. Assumed time scaling maps accelerated cell seconds into line timing. Cell faults quarantine units; defects and one extra rework operator are included.",
  };
  text(
    "scenario-note",
    notes[el("scenario").value] ||
      "Fixed staffing and finite buffers with ±20% cycle variation. No failures or defects; operators attend the entire cycle.",
  );
}
el("scenario").addEventListener("change", scenarioNote);
el("experiment").addEventListener("submit", async (event) => {
  event.preventDefault();
  el("run").disabled = true;
  text("status", "Running virtual shifts…");
  try {
    const body = {
      scenario: el("scenario").value,
      operators: Number(el("operators").value),
      replications: Number(el("replications").value),
      target: Number(el("target").value),
      seed: Number(el("seed").value),
      request_id: crypto.randomUUID(),
    };
    const result = await api("/api/experiments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    render(result);
    await history();
    text(
      "status",
      "Experiment complete. Results and reproduction inputs are saved.",
    );
  } catch (error) {
    text("status", error.message);
  } finally {
    el("run").disabled = false;
  }
});
(async () => {
  try {
    for (const scenario of await api("/api/scenarios")) {
      labels[scenario.id] = scenario.label;
      const option = document.createElement("option");
      option.value = scenario.id;
      option.textContent = scenario.label;
      el("scenario").append(option);
    }
    el("scenario").value = "quality_rework";
    scenarioNote();
    await history();
  } catch (error) {
    text("status", `Could not load the experiment service: ${error.message}`);
    el("run").disabled = true;
  }
})();
