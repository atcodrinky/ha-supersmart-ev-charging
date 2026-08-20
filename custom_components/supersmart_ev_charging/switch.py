"""Switch platform for SuperSmart EV Charging."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    SWITCH_MASTER_STOP,
    SWITCH_FORCE_CHARGE,
    SWITCH_SOLAR_CONTROLLER,
    SWITCH_NIGHT_CHARGING,
)
from .coordinator import SuperSmartEvChargingCoordinator

_LOGGER = logging.getLogger(__name__)

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
        MasterStopSwitch(coordinator, entry),
        ForceChargeSwitch(coordinator, entry),
        SolarControllerSwitch(coordinator, entry),
        NightChargingSwitch(coordinator, entry),
    ])


class _Base(CoordinatorEntity[SuperSmartEvChargingCoordinator], SwitchEntity):
    _attr_has_entity_name = True

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


class MasterStopSwitch(_Base):
    """
    Replica input_boolean.ev_master_stop.
    ON  → ferma tutto, revoca auth, FV OFF, FORZA OFF.
    OFF → si resetta da solo quando il cavo viene scollegato (wallbox → idle).
    """
    _attr_icon = "mdi:stop-circle"

    def __init__(self, c, e):
        super().__init__(c, e, SWITCH_MASTER_STOP)

    @property
    def is_on(self) -> bool:
        return self.coordinator.master_stop

    async def async_turn_on(self, **kwargs: Any) -> None:
        _LOGGER.warning("[SuperSmart] Master Stop ABILITATO – tutta la ricarica bloccata")
        self.coordinator.master_stop    = True
        self.coordinator.force_charge   = False
        self.coordinator.solar_controller_active = False
        # Invia immediatamente set_mode=3 + revoca (replica la sequenza YAML)
        await self.coordinator._set_mode(self.coordinator._payload_pause)
        import asyncio; await asyncio.sleep(2)
        await self.coordinator._revoke()
        self.coordinator.charging_mode = "master_stop"
        self.coordinator.async_update_listeners()

    async def async_turn_off(self, **kwargs: Any) -> None:
        _LOGGER.info("[SuperSmart] Master Stop DISABILITATO")
        self.coordinator.master_stop = False
        self.coordinator.async_update_listeners()
        await self.coordinator.async_update_charging_logic()


class ForceChargeSwitch(_Base):
    """
    Replica input_boolean.forza_ricarica.
    ON  → avvia mode 2 (normal) + modula entro contratto.
    OFF → esegue "Uscita intelligente da FORZA":
          se FV disponibile → attiva solar controller,
          se F3 notte + SOC basso → continua notturna,
          altrimenti → stop carica.
    """
    _attr_icon = "mdi:flash"

    def __init__(self, c, e):
        super().__init__(c, e, SWITCH_FORCE_CHARGE)

    @property
    def is_on(self) -> bool:
        return self.coordinator.force_charge

    async def async_turn_on(self, **kwargs: Any) -> None:
        if self.coordinator.master_stop:
            _LOGGER.warning("[SuperSmart] Impossibile abilitare FORZA: Master Stop attivo")
            return
        _LOGGER.info("[SuperSmart] FORZA RICARICA abilitata")
        self.coordinator.force_charge = True
        # FORZA ha priorità sul controller FV: evita che le due logiche si blocchino.
        self.coordinator.solar_controller_active = False
        await self.coordinator.async_update_charging_logic()

    async def async_turn_off(self, **kwargs: Any) -> None:
        _LOGGER.info("[SuperSmart] FORZA RICARICA disabilitata – uscita intelligente")
        self.coordinator.force_charge = False
        # Replica EV - Uscita intelligente da FORZA
        await self.coordinator._handle_force_exit()


class SolarControllerSwitch(_Base):
    """
    Replica input_boolean.ev_solar_controller_active.
    Normalmente gestito internamente dal coordinator.
    Può essere letto per status; raramente scritto manualmente.
    """
    _attr_icon = "mdi:solar-power-variant"

    def __init__(self, c, e):
        super().__init__(c, e, SWITCH_SOLAR_CONTROLLER)

    @property
    def is_on(self) -> bool:
        return self.coordinator.solar_controller_active

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.coordinator.solar_controller_active = True
        self.coordinator.async_update_listeners()
        await self.coordinator.async_update_charging_logic(
            trigger_entity="solar_controller"
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.coordinator.solar_controller_active = False
        if self.coordinator.charging_mode == "pv_surplus":
            self.coordinator.charging_mode = "idle"
        self.coordinator.async_update_listeners()
        await self.coordinator.async_update_charging_logic()


class NightChargingSwitch(_Base):
    """Abilita/disabilita la logica notturna F3 (Gestione Fascia + Gestione Carichi)."""
    _attr_icon = "mdi:weather-night"

    def __init__(self, c, e):
        super().__init__(c, e, SWITCH_NIGHT_CHARGING)

    @property
    def is_on(self) -> bool:
        return self.coordinator.night_charging_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.coordinator.night_charging_enabled = True
        self.coordinator.async_update_listeners()
        await self.coordinator.async_update_charging_logic()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.coordinator.night_charging_enabled = False
        if self.coordinator.charging_mode == "night":
            await self.coordinator._set_mode(self.coordinator._payload_pause)
            await self.coordinator._revoke()
            self.coordinator.charging_mode = "idle"
        self.coordinator.async_update_listeners()
