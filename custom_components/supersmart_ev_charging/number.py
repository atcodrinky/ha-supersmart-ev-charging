"""Number platform for SuperSmart EV Charging."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    NUMBER_USER_SOC_TARGET,
    NUMBER_VEHICLE_SOC_TARGET,
    NUMBER_CONTRACT_POWER,
    NUMBER_ALLOWED_IMPORT,
    NUMBER_NIGHT_POWER_LIMIT,
    NUMBER_BATTERY_CAPACITY,
    MIN_ALLOWED_IMPORT_W,
    MAX_ALLOWED_IMPORT_W,
)
from .coordinator import SuperSmartEvChargingCoordinator

_DEVICE_INFO = lambda entry: {
    "identifiers": {(DOMAIN, entry.entry_id)},
    "name": entry.title,
    "manufacturer": "atcodrinky",
    "model": "Generic EV Energy Manager",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: SuperSmartEvChargingCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        UserSocTargetNumber(coordinator, entry),
        VehicleSocTargetNumber(coordinator, entry),
        ContractPowerNumber(coordinator, entry),
        AllowedImportNumber(coordinator, entry),
        NightPowerLimitNumber(coordinator, entry),
        BatteryCapacityNumber(coordinator, entry),
    ])


class _Base(CoordinatorEntity[SuperSmartEvChargingCoordinator], NumberEntity):
    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: SuperSmartEvChargingCoordinator,
        entry: ConfigEntry,
        suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id   = f"{entry.entry_id}_{suffix}"
        self._attr_translation_key = suffix
        self._attr_device_info = _DEVICE_INFO(entry)


class UserSocTargetNumber(_Base):
    """
    Replica input_number.limite_batteria_manuale.
    Limite SOC per logica notturna F3. Non può superare limite_auto (Protezione limiti).
    """
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_min_value = 10
    _attr_native_max_value = 100
    _attr_native_step = 5
    _attr_icon = "mdi:battery-charging-50"

    def __init__(self, c, e):
        super().__init__(c, e, NUMBER_USER_SOC_TARGET)

    @property
    def native_value(self) -> float:
        return self.coordinator.user_soc_target

    async def async_set_native_value(self, value: float) -> None:
        # Protezione limiti: limite_manuale non può superare limite_auto
        capped = min(value, self.coordinator.vehicle_soc_target)
        self.coordinator.user_soc_target = capped
        self.coordinator.async_update_listeners()
        await self.coordinator.async_update_charging_logic()


class VehicleSocTargetNumber(_Base):
    """
    Replica input_number.limite_batteria_auto (sincronizzato con number.elroq_limite_di_carica).
    Limite SOC assoluto: stop totale quando raggiunto.
    """
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_min_value = 20
    _attr_native_max_value = 100
    _attr_native_step = 5
    _attr_icon = "mdi:battery-charging-100"

    def __init__(self, c, e):
        super().__init__(c, e, NUMBER_VEHICLE_SOC_TARGET)

    @property
    def native_value(self) -> float:
        return self.coordinator.vehicle_soc_target

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_vehicle_soc_target(value)


class ContractPowerNumber(_Base):
    """
    Replica input_number.limite_potenza_contratto_w.
    Usato da Gestione Carichi (FORZA) per la modulazione.
    """
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_min_value = 1500
    _attr_native_max_value = 22000
    _attr_native_step = 100
    _attr_icon = "mdi:transmission-tower"

    def __init__(self, c, e):
        super().__init__(c, e, NUMBER_CONTRACT_POWER)

    @property
    def native_value(self) -> float:
        return self.coordinator._contract_power_w

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator._contract_power_w = value
        self.coordinator.async_update_listeners()
        await self.coordinator.async_update_charging_logic()


class AllowedImportNumber(_Base):
    """
    Replica input_number.limite_import_permesso.
    Offset aggiunto al surplus FV calcolato: amp_fv = (-rete + offset_w) / v_grid.
    Default 200W = permetti max 200W di import dalla rete mentre carichi con FV.
    Un valore negativo mantiene invece un margine di esportazione: -200W cerca
    di cedere circa 200W alla rete per assorbire le oscillazioni senza importare.
    """
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_min_value = MIN_ALLOWED_IMPORT_W
    _attr_native_max_value = MAX_ALLOWED_IMPORT_W
    _attr_native_step = 50
    _attr_icon = "mdi:transmission-tower-import"

    def __init__(self, c, e):
        super().__init__(c, e, NUMBER_ALLOWED_IMPORT)

    @property
    def native_value(self) -> float:
        return self.coordinator.allowed_import_w

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.allowed_import_w = max(
            MIN_ALLOWED_IMPORT_W, min(value, MAX_ALLOWED_IMPORT_W)
        )
        self.coordinator.async_update_listeners()
        await self.coordinator.async_update_charging_logic()


class NightPowerLimitNumber(_Base):
    """
    Replica input_number.ev_limite_notturno_w.
    Limite di potenza usato in F3 notte da Gestione Fascia e Gestione Carichi
    (NON il limite contrattuale completo – più basso per non disturbare la casa di notte).
    """
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_min_value = 1000
    _attr_native_max_value = 22000
    _attr_native_step = 100
    _attr_icon = "mdi:weather-night"

    def __init__(self, c, e):
        super().__init__(c, e, NUMBER_NIGHT_POWER_LIMIT)

    @property
    def native_value(self) -> float:
        return self.coordinator.night_power_limit_w

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.night_power_limit_w = value
        self.coordinator.async_update_listeners()
        await self.coordinator.async_update_charging_logic()


class BatteryCapacityNumber(_Base):
    """Usable battery capacity used by charging-time estimates."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_native_min_value = 1
    _attr_native_max_value = 250
    _attr_native_step = 0.1
    _attr_icon = "mdi:car-battery"

    def __init__(self, c, e):
        super().__init__(c, e, NUMBER_BATTERY_CAPACITY)

    @property
    def native_value(self) -> float:
        return self.coordinator._battery_capacity_kwh

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_battery_capacity(value)
