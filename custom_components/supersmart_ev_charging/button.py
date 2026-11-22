"""Button platform for atomic scheduled-departure editing."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BUTTON_CANCEL_DEPARTURE,
    BUTTON_CONFIRM_DEPARTURE,
    DOMAIN,
)
from .coordinator import SuperSmartEvChargingCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        ConfirmDepartureButton(coordinator, entry),
        CancelDepartureEditButton(coordinator, entry),
    ])


class _BaseDepartureButton(
    CoordinatorEntity[SuperSmartEvChargingCoordinator], ButtonEntity
):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, suffix: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._attr_translation_key = suffix
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "atcodrinky",
            "model": "Generic EV Energy Manager",
        }


class ConfirmDepartureButton(_BaseDepartureButton):
    _attr_icon = "mdi:calendar-check"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, BUTTON_CONFIRM_DEPARTURE)

    async def async_press(self) -> None:
        await self.coordinator.async_confirm_departure_time()


class CancelDepartureEditButton(_BaseDepartureButton):
    _attr_icon = "mdi:calendar-remove"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, BUTTON_CANCEL_DEPARTURE)

    async def async_press(self) -> None:
        await self.coordinator.async_cancel_departure_time_edit()
