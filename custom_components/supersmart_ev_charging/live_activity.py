"""Helpers for Companion App Live Activities and Android Live Updates."""
from __future__ import annotations

from datetime import datetime
from typing import Any


MODE_COLORS = {
    "fv_surplus": "#4CAF50",
    "notturna_f3": "#2196F3",
    "forza": "#FF9800",
    "sconosciuta": "#607D8B",
}


def soc_bucket(soc: float, step: int) -> int:
    """Return the lower bound of the SOC band containing ``soc``."""
    safe_step = max(1, int(step))
    bounded_soc = min(100, max(0, int(soc)))
    return bounded_soc // safe_step * safe_step


def live_activity_tag(entry_id: str) -> str:
    """Build a stable, valid tag that is unique per config entry."""
    return f"supersmart_ev_{entry_id}"[:64]


def build_live_payload(
    *,
    title: str,
    message: str,
    tag: str,
    soc: int | None,
    target: int,
    mode: str,
    remaining_minutes: float | None,
    dashboard_url: str,
    silent: bool,
    critical_text: str | None = None,
) -> dict[str, Any]:
    """Return the notify payload shared by iOS and Android Companion Apps."""
    color = MODE_COLORS.get(mode, MODE_COLORS["sconosciuta"])
    nested: dict[str, Any] = {
        "tag": tag,
        "live_update": True,
        "notification_icon": "mdi:ev-station",
        "notification_icon_color": color,
        "progress_bar_color": color,
        "color": color,
    }
    if soc is not None:
        nested.update({
            "critical_text": critical_text or f"🔋 {soc}%",
            "progress": min(100, max(0, int(soc))),
            "progress_max": 100,
        })
    if remaining_minutes is not None and remaining_minutes > 0:
        nested.update({
            "chronometer": True,
            "when": max(1, round(remaining_minutes * 60)),
            "when_relative": True,
        })
    if dashboard_url.strip():
        nested["url"] = dashboard_url.strip()
    if silent:
        nested["silent"] = True
    return {"title": title, "message": message, "data": nested}


def end_time_shifted(
    previous: datetime | None,
    current: datetime | None,
    threshold_minutes: int,
) -> bool:
    """Return whether the estimated end changed enough to merit a push."""
    if previous is None or current is None:
        return previous != current
    return abs((current - previous).total_seconds()) >= threshold_minutes * 60
