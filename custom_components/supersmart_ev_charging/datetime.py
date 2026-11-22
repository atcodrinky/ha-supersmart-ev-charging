"""Date/time platform for scheduled departure."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATETIME_DEPARTURE_DRAFT, DATETIME_DEPARTURE_TIME, DOMAIN
from .coordinator import SuperSmartEvChargingCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        DepartureTimeEntity(coordinator, entry),
        DepartureTimeDraftEntity(coordinator, entry),
    ])


class DepartureTimeEntity(CoordinatorEntity[SuperSmartEvChargingCoordinator], DateTimeEntity):
    _attr_has_entity_name = True
    _attr_translation_key = DATETIME_DEPARTURE_TIME
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{DATETIME_DEPARTURE_TIME}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "atcodrinky",
            "model": "Generic EV Energy Manager",
        }

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.departure_time

    async def async_set_value(self, value: datetime) -> None:
        await self.coordinator.async_set_departure_time(value)


class DepartureTimeDraftEntity(
    CoordinatorEntity[SuperSmartEvChargingCoordinator], DateTimeEntity
):
    """Editable buffer that never changes charging until it is confirmed."""

    _attr_has_entity_name = True
    _attr_translation_key = DATETIME_DEPARTURE_DRAFT
    _attr_icon = "mdi:calendar-edit"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{DATETIME_DEPARTURE_DRAFT}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "atcodrinky",
            "model": "Generic EV Energy Manager",
        }

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.departure_time_draft

    async def async_set_value(self, value: datetime) -> None:
        await self.coordinator.async_set_departure_time_draft(value)
