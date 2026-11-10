const $ = (id) => document.getElementById(id);
let report = null;
const money = (n) =>
  n == null
    ? "Undefined"
    : new Intl.NumberFormat("en-IE", {
        style: "currency",
        currency: "EUR",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(n);
const pct = (n) => (n * 100).toFixed(1) + "%";
const categories = [
  ["paid_labor", "Labor", "#54755c"],
  ["energy", "Energy", "#a3b78e"],
  ["consumables", "Consumables", "#cfaa79"],
  ["maintenance_allocation", "Maintenance", "#8c83a7"],
  ["deployment_allocation", "Deployment", "#6695a2"],
  ["incremental_scrap_material_loss", "Scrap material loss", "#ba705e"],
];
function render() {
  if (!report) return;
  const costCase = $("cost-case").value,
    target = $("demand").value,
    rows = $("cost-rows");
  rows.replaceChildren();
  const candidates = [];
  for (const scenario of report.cases) {
    const cost = scenario.cost_sensitivity[costCase],
      demand = scenario.demand_attainment[target],
      qualified = demand.wilson_95_lower >= 0.9;
    if (qualified) candidates.push(scenario);
    const row = document.createElement("tr");
    row.classList.toggle("qualified", qualified);
    const title = document.createElement("td");
    title.textContent = scenario.label;
    const staff = document.createElement("small");
    staff.textContent = `${scenario.production_operators} production + ${scenario.rework_operators} rework operators`;
    title.append(staff);
    row.append(title);
    const values = [
      money(cost.deployment_total_eur),
      scenario.mean_good_units.toFixed(1),
      `${demand.successful_shifts}/${demand.replications}`,
      `${pct(demand.wilson_95_lower)}–${pct(demand.wilson_95_upper)}`,
      money(cost.pooled_conversion_cost_per_good_unit_eur),
      money(cost.demand_capped_cost_per_unit_eur[target]),
    ];
    values.forEach((value, index) => {
      const td = document.createElement("td");
      td.textContent = value;
      if (index === 2 && qualified) {
        const note = document.createElement("span");
        note.className = "qualify";
        note.textContent = "MODEL THRESHOLD MET";
        td.append(note);
      }
      row.append(td);
    });
    rows.append(row);
  }
  if (candidates.length) {
    candidates.sort(
      (a, b) =>
        a.cost_sensitivity[costCase].demand_capped_cost_per_unit_eur[target] -
        b.cost_sensitivity[costCase].demand_capped_cost_per_unit_eur[target],
    );
    const best = candidates[0];
    $("decision").textContent =
      `At ${target} good units per shift, ${candidates.length} configuration${candidates.length === 1 ? " meets" : "s meet"} the modeled reliability threshold. ${best.label} has the lowest demand-capped conversion cost among those cases: ${money(best.cost_sensitivity[costCase].demand_capped_cost_per_unit_eur[target])} per unit. Treat this as a candidate for further validation, not a purchase recommendation.`;
  } else {
    $("decision").textContent =
      `None of these configurations establishes a 90% demand-attainment probability at the selected ${target}-unit target using its 95% lower confidence bound. A low unit cost alone does not resolve the capacity gap.`;
  }
  const bars = $("cost-bars");
  bars.replaceChildren();
  const maximum = Math.max(
    ...report.cases.map(
      (c) => c.cost_sensitivity[costCase].mean_shift_cost_eur,
    ),
  );
  for (const scenario of report.cases) {
    const cost = scenario.cost_sensitivity[costCase],
      row = document.createElement("div");
    row.className = "cost-row";
    const name = document.createElement("span");
    name.textContent = scenario.label;
    const track = document.createElement("div");
    track.className = "cost-track";
    for (const [key, label, color] of categories) {
      const piece = document.createElement("span");
      piece.style.width = (cost.mean_breakdown_eur[key] / maximum) * 100 + "%";
      piece.style.background = color;
      piece.title = label + ": " + money(cost.mean_breakdown_eur[key]);
      track.append(piece);
    }
    const total = document.createElement("strong");
    total.textContent = money(cost.mean_shift_cost_eur);
    row.append(name, track, total);
    bars.append(row);
  }
  const assumptions = report.assumptions,
    preset = assumptions.cost_cases[costCase];
  $("assumptions").textContent =
    `${assumptions.useful_life_years}-year useful life · ${assumptions.operating_days_per_year} days/year · ${assumptions.shifts_per_day} shifts/day · ${pct(assumptions.contingency_fraction)} contingency. Selected labor ${money(preset.labor_rate_eur_per_hour)}/hour; capital multiplier ${preset.capital_multiplier}×; electricity ${money(preset.electricity_eur_per_kwh)}/kWh.`;
  $("cost-status").textContent =
    `${report.total_simulated_shifts.toLocaleString()} simulated shifts · ${report.cases[0].replications} per configuration · identical output reused for all cost cases.`;
}
for (const [key, label, color] of categories) {
  const item = document.createElement("span");
  item.style.setProperty("--color", color);
  item.textContent = label;
  $("cost-legend").append(item);
}
$("cost-case").onchange = render;
$("demand").onchange = render;
(async () => {
  try {
    const response = await fetch("/api/costs");
    report = await response.json();
    if (!response.ok) throw Error(report.error || "Could not load comparison");
    render();
  } catch (error) {
    $("cost-status").textContent = error.message;
  }
})();
