"""Engineering conversion-cost arithmetic using explicit synthetic assumptions."""

import math


def nonnegative(value, name):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(f"{name} must be finite and nonnegative")
    return value


def shift_cost(summary, assumptions, deployment, cost_case):
    for key in ["useful_life_years", "operating_days_per_year", "shifts_per_day"]:
        if nonnegative(assumptions[key], key) <= 0:
            raise ValueError(f"{key} must be positive")
    for key in [
        "maintenance_fraction_of_equipment_per_year",
        "consumables_per_released_unit_eur",
        "rework_consumables_per_attempt_eur",
        "incremental_material_loss_per_scrapped_unit_eur",
        "contingency_fraction",
    ]:
        nonnegative(assumptions[key], key)
    for key, value in cost_case.items():
        nonnegative(value, key)
    components = {k: nonnegative(v, k) for k, v in deployment["components_eur"].items()}
    power = nonnegative(deployment["power_kw"], "power_kw")
    for key in [
        "paid_labor_hours",
        "production_window_s",
        "released_units",
        "rework_started_units",
        "scrapped_units",
        "accepted_units",
    ]:
        nonnegative(summary[key], key)
    multiplier = cost_case["capital_multiplier"]
    direct = sum(components.values()) * multiplier
    contingency = direct * assumptions["contingency_fraction"]
    total_deployment = direct + contingency
    shifts_per_year = (
        assumptions["operating_days_per_year"] * assumptions["shifts_per_day"]
    )
    allocation = total_deployment / (assumptions["useful_life_years"] * shifts_per_year)
    maintenance = (
        components["equipment"]
        * multiplier
        * assumptions["maintenance_fraction_of_equipment_per_year"]
        / shifts_per_year
    )
    breakdown = {
        "paid_labor": summary["paid_labor_hours"]
        * cost_case["labor_rate_eur_per_hour"],
        "energy": power
        * (summary["production_window_s"] / 3600)
        * cost_case["electricity_eur_per_kwh"],
        "consumables": summary["released_units"]
        * assumptions["consumables_per_released_unit_eur"]
        + summary["rework_started_units"]
        * assumptions["rework_consumables_per_attempt_eur"],
        "maintenance_allocation": maintenance,
        "deployment_allocation": allocation,
        "incremental_scrap_material_loss": summary["scrapped_units"]
        * assumptions["incremental_material_loss_per_scrapped_unit_eur"],
    }
    total = sum(breakdown.values())
    good = summary["accepted_units"]
    return {
        "deployment_direct_eur": direct,
        "deployment_contingency_eur": contingency,
        "deployment_total_eur": total_deployment,
        "breakdown_eur": breakdown,
        "shift_cost_eur": total,
        "conversion_cost_per_good_unit_eur": total / good if good else None,
        "payback_years": None,
        "payback_reason": "No substantiated annual cash benefit or contribution margin supplied; extra output is not assumed sold",
    }
