"""SuperSmart EV Charging – generic Home Assistant integration."""
from __future__ import annotations

import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    DOMAIN,
    DEFAULT_MIN_CHARGE_CURRENT_A,
    DEFAULT_MAX_LOAD_CURRENT_A,
)
from .coordinator import SuperSmartEvChargingCoordinator
from .service_helpers import resolve_service_instance

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
]

SERVICE_NAMES = ("authorize_charging", "revoke_charging", "set_charge_limit")


def _service_coordinator(
    hass: HomeAssistant, call: ServiceCall
) -> SuperSmartEvChargingCoordinator:
    """Return the selected coordinator or raise a clear action error."""
    try:
        return resolve_service_instance(
            hass.data.get(DOMAIN, {}), call.data.get(ATTR_CONFIG_ENTRY_ID)
        )
    except ValueError as err:
        raise ServiceValidationError(
            "Select a SuperSmart EV Charging instance when more than one is configured"
        ) from err


def _register_services(hass: HomeAssistant) -> None:
    """Register domain actions once and route calls to the selected instance."""
    if hass.services.has_service(DOMAIN, "authorize_charging"):
        return

    async def svc_authorize(call: ServiceCall) -> None:
        await _service_coordinator(hass, call).authorize_charging()

    async def svc_revoke(call: ServiceCall) -> None:
        await _service_coordinator(hass, call).revoke_charging()

    async def svc_set_limit(call: ServiceCall) -> None:
        await _service_coordinator(hass, call).set_current_limit(
            call.data.get("current_a", DEFAULT_MIN_CHARGE_CURRENT_A)
        )

    instance_schema = {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): str,
    }
    hass.services.async_register(
        DOMAIN,
        "authorize_charging",
        svc_authorize,
        schema=vol.Schema(instance_schema),
    )
    hass.services.async_register(
        DOMAIN,
        "revoke_charging",
        svc_revoke,
        schema=vol.Schema(instance_schema),
    )
    hass.services.async_register(
        DOMAIN,
        "set_charge_limit",
        svc_set_limit,
        schema=vol.Schema({
            **instance_schema,
            vol.Required("current_a"): vol.All(
                vol.Coerce(float),
                vol.Range(
                    min=DEFAULT_MIN_CHARGE_CURRENT_A,
                    max=DEFAULT_MAX_LOAD_CURRENT_A,
                ),
            ),
        }),
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SuperSmart EV Charging from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = SuperSmartEvChargingCoordinator(hass, entry)
    await coordinator.async_restore_state()
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _register_services(hass)

    # ── Background charging loop (every 30 s)
    entry.async_on_unload(
        async_track_time_interval(
            hass,
            coordinator.async_update_charging_logic,
            timedelta(seconds=30),
        )
    )

    # Le automazioni originali reagiscono ai cambi di stato, non solo a un poll.
    tracked_entities = {
        coordinator._soc_entity,
        coordinator._charge_limit_entity,
        coordinator._connected_entity,
        coordinator._wallbox_state_entity,
        coordinator._wallbox_power_entity,
        coordinator._wallbox_voltage_entity,
        coordinator._grid_entity,
        coordinator._pv_entity,
        coordinator._total_power_entity,
        coordinator._tariff_entity,
        "sun.sun",
    }

    @callback
    def _handle_state_change(event: Event) -> None:
        old = event.data.get("old_state")
        new = event.data.get("new_state")
        if new is None:
            return
        coordinator.schedule_state_change(
            event.data["entity_id"],
            old.state if old is not None else "",
            new.state,
        )

    entry.async_on_unload(
        async_track_state_change_event(hass, sorted(e for e in tracked_entities if e), _handle_state_change)
    )

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    # Valutazione iniziale senza bloccare il setup: un broker MQTT o un button
    # momentaneamente non disponibile non deve impedire la creazione del
    # dispositivo e delle entità in Home Assistant.
    hass.async_create_task(coordinator.async_update_charging_logic())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator is not None:
        await coordinator.async_shutdown()
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            for service in SERVICE_NAMES:
                if hass.services.has_service(DOMAIN, service):
                    hass.services.async_remove(DOMAIN, service)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
