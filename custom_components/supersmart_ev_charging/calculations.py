"""Pure calculations shared by the coordinator and its regression tests."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import NamedTuple


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
        or charging_mode in ("force", "pv_surplus", "scheduled_departure")
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


class DeparturePlan(NamedTuple):
    """Pure scheduled-departure calculation result."""

    required_energy_kwh: float
    required_minutes: float | None
    scheduled_start: datetime | None
    projected_end: datetime | None
    delay_minutes: float | None


def scheduled_departure_plan(
    *,
    now: datetime,
    departure_time: datetime,
    current_soc: float,
    target_soc: float,
    usable_capacity_kwh: float,
    charging_efficiency_percent: float,
    available_power_w: float,
    safety_margin_minutes: float,
) -> DeparturePlan:
    """Calculate energy, latest safe start and projected completion.

    Battery capacity represents usable DC energy while wallbox power is AC,
    therefore the configurable efficiency is applied before calculating time.
    """
    efficiency = min(100.0, max(50.0, charging_efficiency_percent)) / 100.0
    required_battery_kwh = max(
        0.0,
        (target_soc - current_soc) / 100.0 * usable_capacity_kwh,
    )
    required_energy_kwh = required_battery_kwh / efficiency
    power_kw = max(0.0, available_power_w) / 1000.0
    if required_energy_kwh <= 0:
        return DeparturePlan(0.0, 0.0, now, now, 0.0)
    if power_kw <= 0.1:
        return DeparturePlan(required_energy_kwh, None, None, None, None)

    required_minutes = required_energy_kwh / power_kw * 60.0
    projected_end = now + timedelta(minutes=required_minutes)
    scheduled_start = departure_time - timedelta(
        minutes=required_minutes + max(0.0, safety_margin_minutes)
    )
    delay_minutes = max(
        0.0,
        (projected_end - departure_time).total_seconds() / 60.0,
    )
    return DeparturePlan(
        required_energy_kwh,
        required_minutes,
        scheduled_start,
        projected_end,
        delay_minutes,
    )


def scheduled_departure_should_override(
    *,
    vehicle_connected: bool,
    now: datetime,
    scheduled_start: datetime | None,
) -> bool:
    """Return whether tariff/PV preferences must be bypassed now.

    The decision deliberately depends only on the newly calculated start time,
    not on the previously active charging mode. This allows moving a deadline
    forward to return the controller to its normal PV/off-peak rules.
    """
    return bool(
        vehicle_connected
        and (scheduled_start is None or now >= scheduled_start)
    )


def departure_draft_is_valid(
    value: datetime | None,
    now: datetime,
) -> bool:
    """Return whether a draft deadline can safely be confirmed."""
    return value is not None and value > now


def soc_below_target(
    soc: float,
    soc_valid: bool,
    target: float,
    allow_without_soc: bool,
) -> bool:
    """Return whether charging may continue below a SOC target.

    With missing SOC, availability-first operation explicitly relies on the
    target stored in the vehicle itself.
    """
    if not soc_valid:
        return allow_without_soc
    return soc < target


def soc_target_reached(soc: float, soc_valid: bool, target: float) -> bool:
    """Never report a target as reached without a valid vehicle SOC."""
    return soc_valid and soc >= target


def night_charge_should_stop(
    charging_mode: str,
    wallbox_charging: bool,
    is_offpeak: bool,
    force_charge: bool,
    solar_controller_active: bool,
) -> bool:
    """Stop a night session when its off-peak window is no longer active."""
    return (
        charging_mode == "night"
        and wallbox_charging
        and not is_offpeak
        and not force_charge
        and not solar_controller_active
    )
