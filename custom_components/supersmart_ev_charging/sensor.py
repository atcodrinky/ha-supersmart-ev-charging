"""Sensor platform for SuperSmart EV Charging."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower, UnitOfElectricCurrent, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    SENSOR_CHARGING_MODE,
    SENSOR_PV_SURPLUS,
    SENSOR_TARGET_SOC,
    SENSOR_TIME_REMAINING,
    SENSOR_CHARGE_END_TIME,
    SENSOR_WALLBOX_CURRENT_TARGET,
)
from .coordinator import SuperSmartEvChargingCoordinator

_DEVICE_INFO = lambda entry_id: {
    "identifiers": {(DOMAIN, entry_id)},
    "name": "SuperSmart EV Charging",
    "manufacturer": "atcodrinky",
    "model": "Generic EV Energy Manager",
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: SuperSmartEvChargingCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        ChargingModeSensor(coordinator, entry),
        PvSurplusSensor(coordinator, entry),
        TargetSocSensor(coordinator, entry),
        TimeRemainingSensor(coordinator, entry),
        ChargeEndTimeSensor(coordinator, entry),
        WallboxCurrentTargetSensor(coordinator, entry),
    ])


class _Base(CoordinatorEntity[SuperSmartEvChargingCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: SuperSmartEvChargingCoordinator, entry: ConfigEntry, suffix: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id  = f"{entry.entry_id}_{suffix}"
        self._attr_device_info = _DEVICE_INFO(entry.entry_id)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success


class ChargingModeSensor(_Base):
    _attr_name = "Charging Mode"
    _attr_icon = "mdi:ev-station"

    def __init__(self, c, e):
        super().__init__(c, e, SENSOR_CHARGING_MODE)

    @property
    def native_value(self) -> str:
        return self.coordinator.charging_mode

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.coordinator.data or {}
        return {
            "vehicle_soc":            d.get("vehicle_soc"),
            "vehicle_connected":      d.get("vehicle_connected"),
            "tariff_value":           d.get("tariff_value"),
            "is_offpeak":             d.get("is_offpeak"),
            "master_stop":            self.coordinator.master_stop,
            "force_charge":           self.coordinator.force_charge,
            "solar_controller_active": self.coordinator.solar_controller_active,
        }


class PvSurplusSensor(_Base):
    _attr_name = "PV Surplus"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class  = SensorDeviceClass.POWER
    _attr_state_class   = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:solar-power"

    def __init__(self, c, e):
        super().__init__(c, e, SENSOR_PV_SURPLUS)

    @property
    def native_value(self) -> float:
        return round(self.coordinator.pv_surplus_w, 1)


class TargetSocSensor(_Base):
    _attr_name = "Target SOC"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class  = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:battery-charging-100"

    def __init__(self, c, e):
        super().__init__(c, e, SENSOR_TARGET_SOC)

    @property
    def native_value(self) -> float:
        return (self.coordinator.data or {}).get("target_soc_active", self.coordinator.vehicle_soc_target)


class TimeRemainingSensor(_Base):
    _attr_name = "Charging Time Remaining"
    _attr_icon = "mdi:timer-outline"

    def __init__(self, c, e):
        super().__init__(c, e, SENSOR_TIME_REMAINING)

    @property
    def native_value(self) -> str | None:
        minutes = (self.coordinator.data or {}).get("remaining_minutes")
        if minutes is None:
            return None
        h, m = int(minutes // 60), int(minutes % 60)
        return f"{h}h {m:02d}m" if h > 0 else f"{m}m"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"remaining_minutes": (self.coordinator.data or {}).get("remaining_minutes")}


class ChargeEndTimeSensor(_Base):
    _attr_name = "Charge End Time"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-end"

    def __init__(self, c, e):
        super().__init__(c, e, SENSOR_CHARGE_END_TIME)

    @property
    def native_value(self) -> datetime | None:
        return (self.coordinator.data or {}).get("charge_end_time")


class WallboxCurrentTargetSensor(_Base):
    _attr_name = "Wallbox Current Target"
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class  = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:current-ac"

    def __init__(self, c, e):
        super().__init__(c, e, SENSOR_WALLBOX_CURRENT_TARGET)

    @property
    def native_value(self) -> float:
        return round((self.coordinator.data or {}).get("wallbox_current_target_a", 0.0), 1)
