"""Tests for routing shared actions across multiple config entries."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


MODULE = (
    Path(__file__).parents[1]
    / "custom_components/supersmart_ev_charging/service_helpers.py"
)
spec = importlib.util.spec_from_file_location("service_helpers", MODULE)
service_helpers = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(service_helpers)


class ServiceInstanceTests(unittest.TestCase):
    def test_single_instance_does_not_require_explicit_target(self) -> None:
        coordinator = object()
        self.assertIs(
            service_helpers.resolve_service_instance({"entry-1": coordinator}, None),
            coordinator,
        )

    def test_multiple_instances_use_selected_config_entry(self) -> None:
        first = object()
        second = object()
        self.assertIs(
            service_helpers.resolve_service_instance(
                {"entry-1": first, "entry-2": second}, "entry-2"
            ),
            second,
        )

    def test_multiple_instances_require_explicit_target(self) -> None:
        with self.assertRaises(ValueError):
            service_helpers.resolve_service_instance(
                {"entry-1": object(), "entry-2": object()}, None
            )

    def test_unknown_or_missing_instance_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            service_helpers.resolve_service_instance({"entry-1": object()}, "missing")
        with self.assertRaises(ValueError):
            service_helpers.resolve_service_instance({}, None)


if __name__ == "__main__":
    unittest.main()
