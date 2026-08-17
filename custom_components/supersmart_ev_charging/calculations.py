"""Pure calculations shared by the coordinator and its regression tests."""
from __future__ import annotations


def clamp_voltage(voltage: float) -> float:
    """Apply the same 180–260 V guard used by the working YAML."""
    value = voltage if voltage > 0 else 230.0
    return float(max(180.0, min(value, 260.0)))


def pv_current_values(
    wallbox_power_w: float,
    grid_power_w: float,
    allowed_import_w: float,
    voltage: float,
) -> tuple[float, float]:
    """Return (grid delta A, final wallbox target A)."""
    safe_v = clamp_voltage(voltage)
    delta_a = (-grid_power_w + allowed_import_w) / safe_v
    target_a = abs(wallbox_power_w) / safe_v + delta_a
    return delta_a, target_a


def wallbox_current_from_power(
    wallbox_power_w: float,
    voltage: float,
) -> float:
    """Estimate the actual single-phase wallbox current from power and voltage."""
    return abs(wallbox_power_w) / clamp_voltage(voltage)


def balanced_current(
    limit_w: float,
    total_power_w: float,
    wallbox_power_w: float,
    voltage: float,
    max_current_a: float,
) -> float:
    """Current available without exceeding the selected power limit."""
    house_w = max(0.0, total_power_w - abs(wallbox_power_w))
    margin_w = max(limit_w - house_w, 0.0)
    return round(min(margin_w / clamp_voltage(voltage), max_current_a), 1)


def active_soc_target(
    charging_mode: str,
    force_charge: bool,
    solar_controller_active: bool,
    user_target: float,
    vehicle_target: float,
) -> float:
    """Return the target used by the active charging strategy."""
    if (
        force_charge
        or solar_controller_active
        or charging_mode in ("force", "pv_surplus")
    ):
        return vehicle_target
    return user_target


def charging_time_minutes(
    current_soc: float,
    target_soc: float,
    usable_capacity_kwh: float,
    wallbox_power_w: float,
) -> float | None:
    """Estimate minutes to target from usable capacity and current AC power."""
    power_kw = abs(wallbox_power_w) / 1000.0
    if power_kw <= 0.1:
        return None
    remaining_kwh = max(
        0.0,
        (target_soc - current_soc) / 100.0 * usable_capacity_kwh,
    )
    return remaining_kwh / power_kw * 60.0
