"""Config flow for SuperSmart EV Charging."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_INSTANCE_NAME,
    CONF_INITIAL_USER_SOC_TARGET,
    CONF_INITIAL_VEHICLE_SOC_TARGET,
    CONF_CONTRACT_POWER_W,
    CONF_BATTERY_CAPACITY_KWH,
    CONF_VEHICLE_SOC_ENTITY,
    CONF_VEHICLE_CHARGE_LIMIT_ENTITY,
    CONF_VEHICLE_CONNECTED_ENTITY,
    CONF_WALLBOX_STATE_ENTITY,
    CONF_WALLBOX_POWER_ENTITY,
    CONF_WALLBOX_VOLTAGE_ENTITY,
    CONF_GRID_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_TOTAL_POWER_ENTITY,
    CONF_BUTTON_AUTHORIZE_ENTITY,
    CONF_BUTTON_REVOKE_ENTITY,
    CONF_TARIFF_ENTITY,
    CONF_TARIFF_OFFPEAK_VALUE,
    CONF_TARIFF_ENABLED,
    CONF_MQTT_ENABLED,
    CONF_MQTT_TOPIC_AUTHORIZE,
    CONF_MQTT_TOPIC_REVOKE,
    CONF_MQTT_TOPIC_SET_CURRENT,
    CONF_MQTT_TOPIC_SET_MODE,
    CONF_MQTT_PAYLOAD_MODE_SOLAR,
    CONF_MQTT_PAYLOAD_MODE_NORMAL,
    CONF_MQTT_PAYLOAD_MODE_PAUSE,
    CONF_ENERGY_PUBLISH_ENABLED,
    CONF_MQTT_TOPIC_POWER_GRID,
    CONF_MQTT_TOPIC_POWER_SOLAR,
    CONF_MQTT_TOPIC_POWER_HOUSE,
    CONF_NOTIFY_SERVICE,
    CONF_NOTIFY_SERVICES,
    CONF_NOTIFICATIONS_ENABLED,
    CONF_NOTIFICATION_LANGUAGE,
    CONF_NOTIFICATION_CUSTOMIZE,
    CONF_NOTIFY_START_TITLE,
    CONF_NOTIFY_START_MESSAGE,
    CONF_NOTIFY_STOP_TITLE,
    CONF_NOTIFY_STOP_MESSAGE,
    CONF_LIVE_ACTIVITY_ENABLED,
    CONF_LIVE_ACTIVITY_SERVICES,
    CONF_LIVE_ACTIVITY_TITLE,
    CONF_LIVE_ACTIVITY_DASHBOARD_URL,
    CONF_LIVE_ACTIVITY_SOC_STEP,
    CONF_LIVE_ACTIVITY_END_BEHAVIOR,
    CONF_LIVE_ACTIVITY_CLEAR_MINUTES,
    CONF_LIVE_ACTIVITY_CUSTOMIZE,
    CONF_LIVE_CRITICAL_TEXT,
    CONF_LIVE_MESSAGE_FORCE,
    CONF_LIVE_MESSAGE_NIGHT,
    CONF_LIVE_MESSAGE_NO_SOC,
    CONF_LIVE_MESSAGE_PV,
    CONF_LIVE_MESSAGE_UNKNOWN,
    CONF_LIVE_STOP_EXTERNAL,
    CONF_LIVE_STOP_LOW_POWER,
    CONF_LIVE_STOP_MANUAL,
    CONF_LIVE_STOP_MASTER,
    CONF_LIVE_STOP_NONE,
    CONF_LIVE_STOP_PV_LOST,
    CONF_LIVE_STOP_USER_TARGET,
    CONF_LIVE_STOP_VEHICLE_TARGET,
    LIVE_CHARGING_TEMPLATE_KEYS,
    LIVE_STOP_TEMPLATE_KEYS,
    CONF_WALLBOX_MODE_ENTITY,
    DEFAULT_CONTRACT_POWER_W,
    DEFAULT_BATTERY_CAPACITY_KWH,
    DEFAULT_MQTT_TOPIC_AUTHORIZE,
    DEFAULT_MQTT_TOPIC_REVOKE,
    DEFAULT_MQTT_TOPIC_SET_CURRENT,
    DEFAULT_MQTT_TOPIC_SET_MODE,
    DEFAULT_MQTT_PAYLOAD_MODE_SOLAR,
    DEFAULT_MQTT_PAYLOAD_MODE_NORMAL,
    DEFAULT_MQTT_PAYLOAD_MODE_PAUSE,
    DEFAULT_MQTT_TOPIC_POWER_GRID,
    DEFAULT_MQTT_TOPIC_POWER_SOLAR,
    DEFAULT_MQTT_TOPIC_POWER_HOUSE,
    DEFAULT_TARIFF_OFFPEAK_VALUE,
    DEFAULT_USER_SOC_TARGET,
    DEFAULT_VEHICLE_SOC_TARGET,
    DEFAULT_LIVE_ACTIVITY_SOC_STEP,
    DEFAULT_LIVE_ACTIVITY_CLEAR_MINUTES,
    LIVE_ACTIVITY_END_AUTOMATIC,
    LIVE_ACTIVITY_END_IMMEDIATE,
    LIVE_ACTIVITY_END_MANUAL,
    NOTIFICATION_LANGUAGE_AUTO,
    NOTIFICATION_LANGUAGE_EN,
    NOTIFICATION_LANGUAGE_IT,
)
from .notifications import notification_defaults, validate_notification_template

_LOGGER = logging.getLogger(__name__)

def _available_notify_services(hass) -> list[str]:
    """Return current notify actions for a dropdown, excluding the generic action."""
    services = hass.services.async_services().get("notify", {})
    return sorted(
        f"notify.{service}"
        for service in services
        if service != "send_message"
    )


def _normalize_notify_services(value: Any) -> list[str]:
    """Normalize legacy single-service values and multi-select values."""
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value if item]


def _valid_notify_services(services: list[str]) -> bool:
    """Return whether all selected actions belong to the notify domain."""
    return bool(services) and all(
        service.startswith("notify.") and service.count(".") == 1
        for service in services
    )


def _notify_service_selector(hass) -> selector.SelectSelector:
    """Build a dropdown while retaining manual support for custom notify groups."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=_available_notify_services(hass),
            multiple=True,
            custom_value=True,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _available_mobile_app_services(hass) -> list[str]:
    """Return direct Companion App notify actions."""
    return [
        service
        for service in _available_notify_services(hass)
        if service.startswith("notify.mobile_app_")
    ]


def _mobile_app_service_selector(hass) -> selector.SelectSelector:
    """Build the multi-select used by Live Activity / Live Update."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=_available_mobile_app_services(hass),
            multiple=True,
            custom_value=False,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _valid_mobile_app_services(services: list[str]) -> bool:
    return bool(services) and all(
        service.startswith("notify.mobile_app_") and service.count(".") == 1
        for service in services
    )


def _live_soc_step_selector() -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1,
            max=25,
            step=1,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def _live_end_behavior_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                LIVE_ACTIVITY_END_MANUAL,
                LIVE_ACTIVITY_END_IMMEDIATE,
                LIVE_ACTIVITY_END_AUTOMATIC,
            ],
            translation_key="live_activity_end_behavior",
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _live_clear_minutes_selector() -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1,
            max=480,
            step=1,
            unit_of_measurement="min",
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def _notification_language_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                NOTIFICATION_LANGUAGE_AUTO,
                NOTIFICATION_LANGUAGE_IT,
                NOTIFICATION_LANGUAGE_EN,
            ],
            translation_key="notification_language",
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _validate_message_fields(user_input: dict[str, Any]) -> bool:
    try:
        for key in (
            CONF_NOTIFY_START_TITLE,
            CONF_NOTIFY_START_MESSAGE,
            CONF_NOTIFY_STOP_TITLE,
            CONF_NOTIFY_STOP_MESSAGE,
        ):
            validate_notification_template(str(user_input[key]))
    except (KeyError, ValueError):
        return False
    return True


def _validate_live_message_fields(
    user_input: dict[str, Any], keys: tuple[str, ...]
) -> bool:
    try:
        for key in keys:
            validate_notification_template(str(user_input[key]))
    except (KeyError, ValueError):
        return False
    return True


class SuperSmartEvChargingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Multi-step config flow for SuperSmart EV Charging:
    Step 1 – General settings (power, battery, SOC targets, feature flags)
    Step 2 – Entity selection (vehicle, wallbox, energy sensors)
    Optional – Notifications (recipients, language, custom messages)
    Final – MQTT configuration (topics and payloads)
    """

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    # ── Step 1: General settings ───────────────────────────────────────────────
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            instance_name = str(user_input.get(CONF_INSTANCE_NAME, "")).strip()
            existing_names = {
                entry.title.casefold() for entry in self._async_current_entries()
            }
            if not instance_name:
                errors[CONF_INSTANCE_NAME] = "instance_name_required"
            elif instance_name.casefold() in existing_names:
                errors[CONF_INSTANCE_NAME] = "instance_name_exists"
            else:
                user_input[CONF_INSTANCE_NAME] = instance_name
                self._data.update(user_input)
                return await self.async_step_entities()

        entry_number = len(self._async_current_entries()) + 1
        default_name = (
            "SuperSmart EV Charging"
            if entry_number == 1
            else f"SuperSmart EV {entry_number} Charging"
        )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_INSTANCE_NAME, default=default_name): selector.TextSelector(),
                vol.Required(CONF_CONTRACT_POWER_W,             default=DEFAULT_CONTRACT_POWER_W):    vol.Coerce(int),
                vol.Required(CONF_BATTERY_CAPACITY_KWH,         default=DEFAULT_BATTERY_CAPACITY_KWH): vol.All(vol.Coerce(float), vol.Range(min=1, max=250)),
                vol.Required(CONF_INITIAL_USER_SOC_TARGET,      default=DEFAULT_USER_SOC_TARGET):     vol.All(vol.Coerce(int), vol.Range(min=10, max=100)),
                vol.Required(CONF_INITIAL_VEHICLE_SOC_TARGET,   default=DEFAULT_VEHICLE_SOC_TARGET):  vol.All(vol.Coerce(int), vol.Range(min=20, max=100)),
                vol.Required(CONF_TARIFF_ENABLED,               default=True): bool,
                vol.Required(CONF_MQTT_ENABLED,                 default=True): bool,
                vol.Required(CONF_ENERGY_PUBLISH_ENABLED,       default=True): bool,
                vol.Required(CONF_NOTIFICATIONS_ENABLED,        default=False): bool,
                vol.Required(CONF_LIVE_ACTIVITY_ENABLED,        default=False): bool,
            }),
            errors=errors,
        )

    # ── Step 2: Entity selection ───────────────────────────────────────────────
    async def async_step_entities(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            configured_vehicle_entities = {
                entry.data.get(CONF_VEHICLE_SOC_ENTITY)
                for entry in self._async_current_entries()
            }
            configured_wallbox_entities = {
                entry.data.get(CONF_WALLBOX_STATE_ENTITY)
                for entry in self._async_current_entries()
            }
            if (
                user_input.get(CONF_VEHICLE_SOC_ENTITY)
                in configured_vehicle_entities
                or user_input.get(CONF_WALLBOX_STATE_ENTITY)
                in configured_wallbox_entities
            ):
                errors["base"] = "vehicle_or_wallbox_already_configured"
            else:
                self._data.update(user_input)
                if self._data.get(CONF_NOTIFICATIONS_ENABLED):
                    return await self.async_step_notifications()
                if self._data.get(CONF_LIVE_ACTIVITY_ENABLED):
                    return await self.async_step_live_activity()
                return await self._finish_optional_steps()

        schema_fields: dict = {
            vol.Required(CONF_VEHICLE_SOC_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            # Per Silla Prism la connessione è derivata da sensor.silla_prism_stato_wallbox
            # (idle = non connesso). Accetta sia binary_sensor sia sensor.
            vol.Optional(CONF_VEHICLE_CONNECTED_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["binary_sensor", "sensor"])
            ),
            vol.Optional(CONF_VEHICLE_CHARGE_LIMIT_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["number", "input_number"])
            ),
            vol.Required(CONF_GRID_POWER_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            # sensor.fotovoltaico_power – OBBLIGATORIO.
            # Usato sia per il calcolo del surplus FV (amp_fv) sia per derivare
            # potenza_istantanea = rete_power + fotovoltaico_power
            vol.Required(CONF_PV_POWER_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            # sensor.potenza_istantanea – OPZIONALE.
            # Se omesso viene calcolato come rete_power + fotovoltaico_power (stesso risultato).
            vol.Optional(CONF_TOTAL_POWER_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            # sensor.silla_prism_stato_wallbox – OBBLIGATORIO.
            # Valori attesi: idle, waiting, pause, charging
            vol.Required(CONF_WALLBOX_STATE_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(CONF_WALLBOX_POWER_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(CONF_WALLBOX_VOLTAGE_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(CONF_WALLBOX_MODE_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            # button.silla_prism_autorizza_ricarica
            vol.Optional(CONF_BUTTON_AUTHORIZE_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="button")
            ),
            # button.silla_prism_revoca_autorizzazione_ricarica
            vol.Optional(CONF_BUTTON_REVOKE_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="button")
            ),
        }

        if self._data.get(CONF_TARIFF_ENABLED):
            schema_fields[vol.Required(CONF_TARIFF_ENTITY)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor", "input_select"])
            )
            schema_fields[vol.Optional(CONF_TARIFF_OFFPEAK_VALUE, default=DEFAULT_TARIFF_OFFPEAK_VALUE)] = str

        return self.async_show_form(
            step_id="entities",
            data_schema=vol.Schema(schema_fields),
            errors=errors,
        )

    # ── Optional notifications ────────────────────────────────────────────────
    async def async_step_notifications(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            services = _normalize_notify_services(user_input.get(CONF_NOTIFY_SERVICES))
            if not _valid_notify_services(services):
                errors["base"] = "notification_destination_required"
            else:
                user_input[CONF_NOTIFY_SERVICES] = services
                self._data.update(user_input)
                if user_input.get(CONF_NOTIFICATION_CUSTOMIZE):
                    return await self.async_step_notification_messages()
                return await self._finish_notification_steps()

        legacy = self._data.get(CONF_NOTIFY_SERVICE, "")
        selected_services = _normalize_notify_services(
            self._data.get(CONF_NOTIFY_SERVICES, legacy)
        )
        return self.async_show_form(
            step_id="notifications",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_NOTIFY_SERVICES,
                    default=selected_services,
                ): _notify_service_selector(self.hass),
                vol.Required(
                    CONF_NOTIFICATION_LANGUAGE,
                    default=self._data.get(
                        CONF_NOTIFICATION_LANGUAGE, NOTIFICATION_LANGUAGE_AUTO
                    ),
                ): _notification_language_selector(),
                vol.Required(
                    CONF_NOTIFICATION_CUSTOMIZE,
                    default=self._data.get(CONF_NOTIFICATION_CUSTOMIZE, False),
                ): selector.BooleanSelector(),
            }),
            errors=errors,
        )

    async def async_step_notification_messages(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if _validate_message_fields(user_input):
                self._data.update(user_input)
                return await self._finish_notification_steps()
            errors["base"] = "invalid_notification_template"

        defaults = notification_defaults(
            self._data.get(CONF_NOTIFICATION_LANGUAGE, NOTIFICATION_LANGUAGE_AUTO),
            self.hass.config.language,
        )
        values = user_input or self._data
        return self.async_show_form(
            step_id="notification_messages",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_NOTIFY_START_TITLE,
                    default=values.get(CONF_NOTIFY_START_TITLE, defaults["start_title"]),
                ): selector.TextSelector(),
                vol.Required(
                    CONF_NOTIFY_START_MESSAGE,
                    default=values.get(CONF_NOTIFY_START_MESSAGE, defaults["start_message"]),
                ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
                vol.Required(
                    CONF_NOTIFY_STOP_TITLE,
                    default=values.get(CONF_NOTIFY_STOP_TITLE, defaults["stop_title"]),
                ): selector.TextSelector(),
                vol.Required(
                    CONF_NOTIFY_STOP_MESSAGE,
                    default=values.get(CONF_NOTIFY_STOP_MESSAGE, defaults["stop_message"]),
                ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
            }),
            errors=errors,
            description_placeholders={
                "placeholders": "{instance}, {mode}, {soc}, {target}, {time_remaining}, {charge_end_time}"
            },
        )

    async def _finish_notification_steps(self) -> FlowResult:
        if self._data.get(CONF_LIVE_ACTIVITY_ENABLED):
            return await self.async_step_live_activity()
        return await self._finish_optional_steps()

    async def async_step_live_activity(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure Companion App Live Activity / Live Update."""
        errors: dict[str, str] = {}
        if user_input is not None:
            services = _normalize_notify_services(
                user_input.get(CONF_LIVE_ACTIVITY_SERVICES)
            )
            if not _valid_mobile_app_services(services):
                errors["base"] = "live_activity_destination_required"
            else:
                user_input[CONF_LIVE_ACTIVITY_SERVICES] = services
                user_input[CONF_LIVE_ACTIVITY_TITLE] = (
                    str(user_input.get(CONF_LIVE_ACTIVITY_TITLE, "")).strip()
                    or self._data[CONF_INSTANCE_NAME]
                )
                user_input[CONF_LIVE_ACTIVITY_DASHBOARD_URL] = str(
                    user_input.get(CONF_LIVE_ACTIVITY_DASHBOARD_URL, "")
                ).strip()
                self._data.update(user_input)
                return await self._finish_optional_steps()

        return self.async_show_form(
            step_id="live_activity",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_LIVE_ACTIVITY_SERVICES,
                    default=_normalize_notify_services(
                        self._data.get(CONF_LIVE_ACTIVITY_SERVICES)
                    ),
                ): _mobile_app_service_selector(self.hass),
                vol.Required(
                    CONF_LIVE_ACTIVITY_TITLE,
                    default=self._data.get(
                        CONF_LIVE_ACTIVITY_TITLE,
                        self._data.get(CONF_INSTANCE_NAME, "SuperSmart EV Charging"),
                    ),
                ): selector.TextSelector(),
                vol.Required(
                    CONF_LIVE_ACTIVITY_SOC_STEP,
                    default=self._data.get(
                        CONF_LIVE_ACTIVITY_SOC_STEP,
                        DEFAULT_LIVE_ACTIVITY_SOC_STEP,
                    ),
                ): _live_soc_step_selector(),
                vol.Required(
                    CONF_LIVE_ACTIVITY_END_BEHAVIOR,
                    default=self._data.get(
                        CONF_LIVE_ACTIVITY_END_BEHAVIOR,
                        LIVE_ACTIVITY_END_AUTOMATIC,
                    ),
                ): _live_end_behavior_selector(),
                vol.Required(
                    CONF_LIVE_ACTIVITY_CLEAR_MINUTES,
                    default=self._data.get(
                        CONF_LIVE_ACTIVITY_CLEAR_MINUTES,
                        DEFAULT_LIVE_ACTIVITY_CLEAR_MINUTES,
                    ),
                ): _live_clear_minutes_selector(),
                vol.Optional(
                    CONF_LIVE_ACTIVITY_DASHBOARD_URL,
                    default=self._data.get(CONF_LIVE_ACTIVITY_DASHBOARD_URL, ""),
                ): selector.TextSelector(),
            }),
            errors=errors,
        )

    async def _finish_optional_steps(self) -> FlowResult:
        if self._data.get(CONF_MQTT_ENABLED):
            return await self.async_step_mqtt()
        return self._create_entry()

    # ── Step 3: MQTT configuration ─────────────────────────────────────────────
    async def async_step_mqtt(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return self._create_entry()

        return self.async_show_form(
            step_id="mqtt",
            data_schema=vol.Schema({
                vol.Required(CONF_MQTT_TOPIC_AUTHORIZE,   default=DEFAULT_MQTT_TOPIC_AUTHORIZE):   str,
                vol.Required(CONF_MQTT_TOPIC_REVOKE,      default=DEFAULT_MQTT_TOPIC_REVOKE):      str,
                vol.Required(CONF_MQTT_TOPIC_SET_CURRENT, default=DEFAULT_MQTT_TOPIC_SET_CURRENT): str,
                vol.Optional(CONF_MQTT_TOPIC_SET_MODE,    default=DEFAULT_MQTT_TOPIC_SET_MODE):    str,
                vol.Optional(CONF_MQTT_PAYLOAD_MODE_SOLAR,   default=DEFAULT_MQTT_PAYLOAD_MODE_SOLAR):   str,
                vol.Optional(CONF_MQTT_PAYLOAD_MODE_NORMAL,  default=DEFAULT_MQTT_PAYLOAD_MODE_NORMAL):  str,
                vol.Optional(CONF_MQTT_PAYLOAD_MODE_PAUSE,   default=DEFAULT_MQTT_PAYLOAD_MODE_PAUSE):   str,
                vol.Optional(CONF_MQTT_TOPIC_POWER_GRID,  default=DEFAULT_MQTT_TOPIC_POWER_GRID):  str,
                vol.Optional(CONF_MQTT_TOPIC_POWER_SOLAR, default=DEFAULT_MQTT_TOPIC_POWER_SOLAR): str,
                vol.Optional(CONF_MQTT_TOPIC_POWER_HOUSE, default=DEFAULT_MQTT_TOPIC_POWER_HOUSE): str,
            }),
        )

    def _create_entry(self) -> FlowResult:
        return self.async_create_entry(
            title=self._data[CONF_INSTANCE_NAME],
            data=self._data,
        )

    # ── Options flow ───────────────────────────────────────────────────────────
    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SuperSmartEvChargingOptionsFlow:
        return SuperSmartEvChargingOptionsFlow(config_entry)


class SuperSmartEvChargingOptionsFlow(config_entries.OptionsFlow):
    """Transactional options flow with an explicit Save & Close action."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        # Compatibile sia con HA recente sia con le versioni in cui la config
        # entry doveva essere conservata esplicitamente dall'options flow.
        self._config_entry = config_entry
        self._pending: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "general",
                "notifications",
                "live_activity",
                "save_and_close",
            ],
            description_placeholders={"instance": self._config_entry.title},
        )

    def _values(self) -> dict[str, Any]:
        """Return config data overlaid with saved and in-flow option values."""
        return {
            **self._config_entry.data,
            **self._config_entry.options,
            **self._pending,
        }

    async def async_step_general(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            self._pending.update(user_input)
            return await self.async_step_init()

        d = self._values()
        return self.async_show_form(
            step_id="general",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_BATTERY_CAPACITY_KWH,
                    default=d.get(CONF_BATTERY_CAPACITY_KWH, DEFAULT_BATTERY_CAPACITY_KWH),
                ): vol.All(vol.Coerce(float), vol.Range(min=1, max=250)),
                vol.Required(
                    CONF_INITIAL_USER_SOC_TARGET,
                    default=d.get(
                        CONF_INITIAL_USER_SOC_TARGET, DEFAULT_USER_SOC_TARGET
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=100)),
                vol.Required(
                    CONF_TARIFF_ENABLED,
                    default=d.get(CONF_TARIFF_ENABLED, True),
                ): bool,
                vol.Required(
                    CONF_MQTT_ENABLED,
                    default=d.get(CONF_MQTT_ENABLED, True),
                ): bool,
                vol.Required(
                    CONF_ENERGY_PUBLISH_ENABLED,
                    default=d.get(CONF_ENERGY_PUBLISH_ENABLED, True),
                ): bool,
            }),
        )

    async def async_step_notifications(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        d = self._values()
        legacy_enabled = bool(d.get(CONF_NOTIFY_SERVICE))
        errors: dict[str, str] = {}
        if user_input is not None:
            enabled = bool(user_input[CONF_NOTIFICATIONS_ENABLED])
            services = _normalize_notify_services(
                user_input.get(CONF_NOTIFY_SERVICES)
            )
            if enabled and not _valid_notify_services(services):
                errors["base"] = "notification_destination_required"
            else:
                user_input[CONF_NOTIFY_SERVICES] = services
                self._pending.update(user_input)
                if not enabled:
                    return await self.async_step_init()
                if user_input.get(CONF_NOTIFICATION_CUSTOMIZE):
                    return await self.async_step_notification_messages()
                return await self.async_step_init()

        legacy = d.get(CONF_NOTIFY_SERVICE, "")
        selected_services = _normalize_notify_services(
            d.get(CONF_NOTIFY_SERVICES, legacy)
        )

        return self.async_show_form(
            step_id="notifications",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_NOTIFICATIONS_ENABLED,
                    default=d.get(CONF_NOTIFICATIONS_ENABLED, legacy_enabled),
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_NOTIFY_SERVICES,
                    default=selected_services,
                ): _notify_service_selector(self.hass),
                vol.Required(
                    CONF_NOTIFICATION_LANGUAGE,
                    default=d.get(
                        CONF_NOTIFICATION_LANGUAGE, NOTIFICATION_LANGUAGE_AUTO
                    ),
                ): _notification_language_selector(),
                vol.Required(
                    CONF_NOTIFICATION_CUSTOMIZE,
                    default=d.get(CONF_NOTIFICATION_CUSTOMIZE, False),
                ): selector.BooleanSelector(),
            }),
            errors=errors,
        )

    async def async_step_notification_messages(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        d = self._values()
        errors: dict[str, str] = {}
        if user_input is not None:
            if _validate_message_fields(user_input):
                self._pending.update(user_input)
                return await self.async_step_init()
            errors["base"] = "invalid_notification_template"

        defaults = notification_defaults(
            d.get(CONF_NOTIFICATION_LANGUAGE, NOTIFICATION_LANGUAGE_AUTO),
            self.hass.config.language,
        )
        values = user_input or d
        return self.async_show_form(
            step_id="notification_messages",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_NOTIFY_START_TITLE,
                    default=values.get(CONF_NOTIFY_START_TITLE, defaults["start_title"]),
                ): selector.TextSelector(),
                vol.Required(
                    CONF_NOTIFY_START_MESSAGE,
                    default=values.get(CONF_NOTIFY_START_MESSAGE, defaults["start_message"]),
                ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
                vol.Required(
                    CONF_NOTIFY_STOP_TITLE,
                    default=values.get(CONF_NOTIFY_STOP_TITLE, defaults["stop_title"]),
                ): selector.TextSelector(),
                vol.Required(
                    CONF_NOTIFY_STOP_MESSAGE,
                    default=values.get(CONF_NOTIFY_STOP_MESSAGE, defaults["stop_message"]),
                ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
            }),
            errors=errors,
            description_placeholders={
                "placeholders": "{instance}, {mode}, {soc}, {target}, {time_remaining}, {charge_end_time}"
            },
        )

    async def async_step_live_activity(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit Live Activity / Live Update options."""
        d = self._values()
        errors: dict[str, str] = {}
        if user_input is not None:
            enabled = bool(user_input[CONF_LIVE_ACTIVITY_ENABLED])
            services = _normalize_notify_services(
                user_input.get(CONF_LIVE_ACTIVITY_SERVICES)
            )
            if enabled and not _valid_mobile_app_services(services):
                errors["base"] = "live_activity_destination_required"
            else:
                user_input[CONF_LIVE_ACTIVITY_SERVICES] = services
                user_input[CONF_LIVE_ACTIVITY_TITLE] = (
                    str(user_input.get(CONF_LIVE_ACTIVITY_TITLE, "")).strip()
                    or self._config_entry.title
                )
                user_input[CONF_LIVE_ACTIVITY_DASHBOARD_URL] = str(
                    user_input.get(CONF_LIVE_ACTIVITY_DASHBOARD_URL, "")
                ).strip()
                self._pending.update(user_input)
                if enabled and user_input.get(CONF_LIVE_ACTIVITY_CUSTOMIZE):
                    return await self.async_step_live_activity_messages()
                return await self.async_step_init()

        return self.async_show_form(
            step_id="live_activity",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_LIVE_ACTIVITY_ENABLED,
                    default=d.get(CONF_LIVE_ACTIVITY_ENABLED, False),
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_LIVE_ACTIVITY_SERVICES,
                    default=_normalize_notify_services(
                        d.get(CONF_LIVE_ACTIVITY_SERVICES)
                    ),
                ): _mobile_app_service_selector(self.hass),
                vol.Required(
                    CONF_LIVE_ACTIVITY_TITLE,
                    default=d.get(CONF_LIVE_ACTIVITY_TITLE, self._config_entry.title),
                ): selector.TextSelector(),
                vol.Required(
                    CONF_LIVE_ACTIVITY_SOC_STEP,
                    default=d.get(
                        CONF_LIVE_ACTIVITY_SOC_STEP,
                        DEFAULT_LIVE_ACTIVITY_SOC_STEP,
                    ),
                ): _live_soc_step_selector(),
                vol.Required(
                    CONF_LIVE_ACTIVITY_END_BEHAVIOR,
                    default=d.get(
                        CONF_LIVE_ACTIVITY_END_BEHAVIOR,
                        LIVE_ACTIVITY_END_AUTOMATIC,
                    ),
                ): _live_end_behavior_selector(),
                vol.Required(
                    CONF_LIVE_ACTIVITY_CLEAR_MINUTES,
                    default=d.get(
                        CONF_LIVE_ACTIVITY_CLEAR_MINUTES,
                        DEFAULT_LIVE_ACTIVITY_CLEAR_MINUTES,
                    ),
                ): _live_clear_minutes_selector(),
                vol.Required(
                    CONF_LIVE_ACTIVITY_CUSTOMIZE,
                    default=d.get(CONF_LIVE_ACTIVITY_CUSTOMIZE, False),
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_LIVE_ACTIVITY_DASHBOARD_URL,
                    default=d.get(CONF_LIVE_ACTIVITY_DASHBOARD_URL, ""),
                ): selector.TextSelector(),
            }),
            errors=errors,
            description_placeholders={"instance": self._config_entry.title},
        )

    async def async_step_live_activity_messages(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Open the Live Activity message customization submenu."""
        return self.async_show_menu(
            step_id="live_activity_messages",
            menu_options=[
                "live_activity_charging_messages",
                "live_activity_stop_messages",
                "live_activity_messages_done",
            ],
        )

    def _live_defaults(self) -> dict[str, Any]:
        values = self._values()
        return notification_defaults(
            values.get(CONF_NOTIFICATION_LANGUAGE, NOTIFICATION_LANGUAGE_AUTO),
            self.hass.config.language,
        )["live_templates"]

    async def async_step_live_activity_charging_messages(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit messages displayed while charging."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if _validate_live_message_fields(user_input, LIVE_CHARGING_TEMPLATE_KEYS):
                self._pending.update(user_input)
                return await self.async_step_live_activity_messages()
            errors["base"] = "invalid_notification_template"
        values = user_input or self._values()
        defaults = self._live_defaults()
        return self.async_show_form(
            step_id="live_activity_charging_messages",
            data_schema=vol.Schema({
                vol.Required(key, default=values.get(key) or defaults[key]):
                    selector.TextSelector(selector.TextSelectorConfig(multiline=True))
                for key in LIVE_CHARGING_TEMPLATE_KEYS
            }),
            errors=errors,
            description_placeholders={
                "placeholders": "{instance}, {mode}, {soc}, {target}, {charge_end_time}"
            },
        )

    async def async_step_live_activity_stop_messages(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit messages displayed after charging stops."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if _validate_live_message_fields(user_input, LIVE_STOP_TEMPLATE_KEYS):
                self._pending.update(user_input)
                return await self.async_step_live_activity_messages()
            errors["base"] = "invalid_notification_template"
        values = user_input or self._values()
        defaults = self._live_defaults()
        return self.async_show_form(
            step_id="live_activity_stop_messages",
            data_schema=vol.Schema({
                vol.Required(key, default=values.get(key) or defaults[key]):
                    selector.TextSelector(selector.TextSelectorConfig(multiline=True))
                for key in LIVE_STOP_TEMPLATE_KEYS
            }),
            errors=errors,
            description_placeholders={
                "placeholders": "{instance}, {mode}, {soc}, {target}, {reason}"
            },
        )

    async def async_step_live_activity_messages_done(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Return to the main options menu while preserving the draft."""
        return await self.async_step_init()

    async def async_step_save_and_close(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Persist the draft once and finish the options flow."""
        return self._save_options(self._pending)

    def _save_options(self, updates: dict[str, Any]) -> FlowResult:
        return self.async_create_entry(
            title="",
            data={**self._config_entry.options, **updates},
        )
