"""Helpers for routing integration actions to the correct config entry."""
from __future__ import annotations

from collections.abc import Mapping
from typing import TypeVar

_T = TypeVar("_T")


def resolve_service_instance(
    instances: Mapping[str, _T], config_entry_id: str | None
) -> _T:
    """Resolve one coordinator, requiring an explicit target when ambiguous."""
    if config_entry_id:
        try:
            return instances[config_entry_id]
        except KeyError as err:
            raise ValueError("configured instance not found") from err

    if len(instances) == 1:
        return next(iter(instances.values()))
    if not instances:
        raise ValueError("no configured instances available")
    raise ValueError("multiple instances configured; select one")
