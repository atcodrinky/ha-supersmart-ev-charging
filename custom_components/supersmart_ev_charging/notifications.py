"""Notification localization and user-template helpers."""
from __future__ import annotations

from string import Formatter
from typing import Any

from .const import (
    NOTIFICATION_LANGUAGE_AUTO,
    NOTIFICATION_LANGUAGE_EN,
    NOTIFICATION_LANGUAGE_IT,
)

ALLOWED_TEMPLATE_FIELDS = {
    "mode",
    "soc",
    "target",
    "time_remaining",
    "charge_end_time",
}

DEFAULT_NOTIFICATION_TEXTS: dict[str, dict[str, Any]] = {
    NOTIFICATION_LANGUAGE_IT: {
        "start_title": "🚗 Ricarica avviata 🚗",
        "start_message": "Modalità: {mode}\nSOC: {soc}%\nTarget: {target}%",
        "stop_title": "🏁 Ricarica terminata 🏁",
        "stop_message": "Modalità: {mode}\nSOC finale: {soc}%",
        "modes": {
            "fv_surplus": "Surplus FV ☀️",
            "notturna_f3": "Notturna F3 🌙",
            "forza": "Forza ⚡",
            "sconosciuta": "Sconosciuta ❓",
        },
    },
    NOTIFICATION_LANGUAGE_EN: {
        "start_title": "🚗 Charging started 🚗",
        "start_message": "Mode: {mode}\nSOC: {soc}%\nTarget: {target}%",
        "stop_title": "🏁 Charging completed 🏁",
        "stop_message": "Mode: {mode}\nFinal SOC: {soc}%",
        "modes": {
            "fv_surplus": "PV surplus ☀️",
            "notturna_f3": "Night / off-peak 🌙",
            "forza": "Force charge ⚡",
            "sconosciuta": "Unknown ❓",
        },
    },
}


def resolve_notification_language(selected: str, hass_language: str) -> str:
    """Resolve Auto/explicit language, with English as the public fallback."""
    if selected == NOTIFICATION_LANGUAGE_IT:
        return NOTIFICATION_LANGUAGE_IT
    if selected == NOTIFICATION_LANGUAGE_EN:
        return NOTIFICATION_LANGUAGE_EN
    if selected == NOTIFICATION_LANGUAGE_AUTO and hass_language.lower().startswith("it"):
        return NOTIFICATION_LANGUAGE_IT
    return NOTIFICATION_LANGUAGE_EN


def notification_defaults(selected: str, hass_language: str) -> dict[str, Any]:
    """Return default strings for the selected or Home Assistant language."""
    language = resolve_notification_language(selected, hass_language)
    return DEFAULT_NOTIFICATION_TEXTS[language]


def validate_notification_template(value: str) -> None:
    """Reject malformed templates and unsupported replacement fields."""
    try:
        fields = {
            field_name
            for _, field_name, _, _ in Formatter().parse(value)
            if field_name is not None
        }
    except ValueError as err:
        raise ValueError("invalid braces") from err
    unsupported = fields - ALLOWED_TEMPLATE_FIELDS
    if unsupported:
        raise ValueError(f"unsupported fields: {', '.join(sorted(unsupported))}")


def render_notification_template(value: str, context: dict[str, Any]) -> str:
    """Render a previously validated notification template."""
    validate_notification_template(value)
    return value.format_map({key: context.get(key, "—") for key in ALLOWED_TEMPLATE_FIELDS})
