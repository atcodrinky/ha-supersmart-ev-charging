"""Notification localization and user-template helpers."""
from __future__ import annotations

from string import Formatter
from typing import Any

from .const import (
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
    NOTIFICATION_LANGUAGE_AUTO,
    NOTIFICATION_LANGUAGE_EN,
    NOTIFICATION_LANGUAGE_IT,
)

ALLOWED_TEMPLATE_FIELDS = {
    "instance",
    "mode",
    "soc",
    "target",
    "time_remaining",
    "charge_end_time",
    "reason",
}

DEFAULT_NOTIFICATION_TEXTS: dict[str, dict[str, Any]] = {
    NOTIFICATION_LANGUAGE_IT: {
        "start_title": "🚗 {instance} – Ricarica avviata 🚗",
        "start_message": "Modalità: {mode}\nSOC: {soc}%\nTarget: {target}%",
        "stop_title": "🏁 {instance} – Ricarica terminata 🏁",
        "stop_message": "Modalità: {mode}\nSOC finale: {soc}%",
        "live_charging": "{mode} · 🎯 {target}% · {charge_end_time}",
        "live_charging_no_end": "{mode} · 🎯 {target}%",
        "live_soc_stale": "{mode} · SOC non disponibile",
        "live_completed": "{reason} · SOC {soc}%",
        "live_templates": {
            CONF_LIVE_MESSAGE_PV: "☀️ FV · 🎯 {target}%\n🕒 {charge_end_time}",
            CONF_LIVE_MESSAGE_NIGHT: "🌙 F3 · 🎯 {target}%\n🕒 {charge_end_time}",
            CONF_LIVE_MESSAGE_FORCE: "💪 MAX · 🎯 {target}%\n🕒 {charge_end_time}",
            CONF_LIVE_MESSAGE_UNKNOWN: "🔌 Ricarica · 🎯 {target}%\n🕒 {charge_end_time}",
            CONF_LIVE_MESSAGE_NO_SOC: "{mode} · SOC non disponibile",
            CONF_LIVE_CRITICAL_TEXT: "🔋 {soc}%",
            CONF_LIVE_STOP_NONE: "✅ Ricarica terminata",
            CONF_LIVE_STOP_MASTER: "🛑 Master Stop",
            CONF_LIVE_STOP_VEHICLE_TARGET: "✅ Ricarica completata\n🎯 Target raggiunto",
            CONF_LIVE_STOP_USER_TARGET: "✅ Ricarica completata\n🎯 Target raggiunto",
            CONF_LIVE_STOP_LOW_POWER: "⚠️ Potenza insufficiente",
            CONF_LIVE_STOP_PV_LOST: "☁️ FV insufficiente",
            CONF_LIVE_STOP_EXTERNAL: "⏹️ Ricarica interrotta\nStop dalla wallbox",
            CONF_LIVE_STOP_MANUAL: "⏹️ Ricarica interrotta\nComando manuale",
        },
        "live_modes": {
            "fv_surplus": "☀️ FV",
            "notturna_f3": "🌙 F3",
            "forza": "💪 MAX",
            "sconosciuta": "🔌 Ricarica",
        },
        "modes": {
            "fv_surplus": "Surplus FV ☀️",
            "notturna_f3": "Notturna F3 🌙",
            "forza": "Forza ⚡",
            "sconosciuta": "Sconosciuta ❓",
        },
        "stop_reasons": {
            "none": "Ricarica terminata",
            "master_stop": "Master Stop",
            "vehicle_target_reached": "Target veicolo raggiunto",
            "user_target_reached": "Target utente raggiunto",
            "low_power_margin": "Margine di potenza insufficiente",
            "pv_surplus_lost": "Surplus FV terminato",
            "wallbox_stopped": "Ricarica fermata dalla wallbox",
            "manual_stop": "Ricarica fermata manualmente",
        },
    },
    NOTIFICATION_LANGUAGE_EN: {
        "start_title": "🚗 {instance} – Charging started 🚗",
        "start_message": "Mode: {mode}\nSOC: {soc}%\nTarget: {target}%",
        "stop_title": "🏁 {instance} – Charging completed 🏁",
        "stop_message": "Mode: {mode}\nFinal SOC: {soc}%",
        "live_charging": "{mode} · 🎯 {target}% · {charge_end_time}",
        "live_charging_no_end": "{mode} · 🎯 {target}%",
        "live_soc_stale": "{mode} · SOC unavailable",
        "live_completed": "{reason} · SOC {soc}%",
        "live_templates": {
            CONF_LIVE_MESSAGE_PV: "☀️ PV · 🎯 {target}%\n🕒 {charge_end_time}",
            CONF_LIVE_MESSAGE_NIGHT: "🌙 Off-peak · 🎯 {target}%\n🕒 {charge_end_time}",
            CONF_LIVE_MESSAGE_FORCE: "💪 MAX · 🎯 {target}%\n🕒 {charge_end_time}",
            CONF_LIVE_MESSAGE_UNKNOWN: "🔌 Charging · 🎯 {target}%\n🕒 {charge_end_time}",
            CONF_LIVE_MESSAGE_NO_SOC: "{mode} · SOC unavailable",
            CONF_LIVE_CRITICAL_TEXT: "🔋 {soc}%",
            CONF_LIVE_STOP_NONE: "✅ Charging ended",
            CONF_LIVE_STOP_MASTER: "🛑 Master Stop",
            CONF_LIVE_STOP_VEHICLE_TARGET: "✅ Charging complete\n🎯 Target reached",
            CONF_LIVE_STOP_USER_TARGET: "✅ Charging complete\n🎯 Target reached",
            CONF_LIVE_STOP_LOW_POWER: "⚠️ Insufficient power",
            CONF_LIVE_STOP_PV_LOST: "☁️ Insufficient PV",
            CONF_LIVE_STOP_EXTERNAL: "⏹️ Charging interrupted\nStopped by wallbox",
            CONF_LIVE_STOP_MANUAL: "⏹️ Charging interrupted\nManual command",
        },
        "live_modes": {
            "fv_surplus": "☀️ PV",
            "notturna_f3": "🌙 Off-peak",
            "forza": "💪 MAX",
            "sconosciuta": "🔌 Charging",
        },
        "modes": {
            "fv_surplus": "PV surplus ☀️",
            "notturna_f3": "Night / off-peak 🌙",
            "forza": "Force charge ⚡",
            "sconosciuta": "Unknown ❓",
        },
        "stop_reasons": {
            "none": "Charging completed",
            "master_stop": "Master Stop",
            "vehicle_target_reached": "Vehicle target reached",
            "user_target_reached": "User target reached",
            "low_power_margin": "Insufficient power margin",
            "pv_surplus_lost": "PV surplus ended",
            "wallbox_stopped": "Charging stopped by wallbox",
            "manual_stop": "Charging stopped manually",
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
