"""Tests for notification localization and custom message templates."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest


PACKAGE = Path(__file__).parents[1] / "custom_components/supersmart_ev_charging"
package = types.ModuleType("supersmart_ev_charging")
package.__path__ = [str(PACKAGE)]
sys.modules.setdefault("supersmart_ev_charging", package)

for module_name in ("const", "notifications"):
    spec = importlib.util.spec_from_file_location(
        f"supersmart_ev_charging.{module_name}", PACKAGE / f"{module_name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)

notifications = sys.modules["supersmart_ev_charging.notifications"]


class NotificationTests(unittest.TestCase):
    def test_auto_language_follows_home_assistant_with_english_fallback(self) -> None:
        self.assertEqual(
            notifications.resolve_notification_language("auto", "it"), "it"
        )
        self.assertEqual(
            notifications.resolve_notification_language("auto", "it-IT"), "it"
        )
        self.assertEqual(
            notifications.resolve_notification_language("auto", "de"), "en"
        )

    def test_explicit_language_overrides_home_assistant(self) -> None:
        self.assertEqual(
            notifications.resolve_notification_language("en", "it"), "en"
        )
        self.assertEqual(
            notifications.resolve_notification_language("it", "en"), "it"
        )

    def test_default_messages_are_localized(self) -> None:
        italian = notifications.notification_defaults("auto", "it")
        english = notifications.notification_defaults("auto", "en")
        self.assertIn("Ricarica avviata", italian["start_title"])
        self.assertIn("Charging started", english["start_title"])
        self.assertIn("{instance}", italian["start_title"])

    def test_custom_template_renders_supported_values(self) -> None:
        rendered = notifications.render_notification_template(
            "{instance} · {mode}: {soc}% → {target}% alle {charge_end_time}",
            {
                "instance": "SuperSmart Elroq Charging",
                "mode": "Surplus FV",
                "soc": 42,
                "target": 80,
                "charge_end_time": "18:30",
            },
        )
        self.assertEqual(
            rendered,
            "SuperSmart Elroq Charging · Surplus FV: 42% → 80% alle 18:30",
        )

    def test_custom_template_rejects_unknown_or_malformed_fields(self) -> None:
        with self.assertRaises(ValueError):
            notifications.validate_notification_template("{unsupported}")
        with self.assertRaises(ValueError):
            notifications.validate_notification_template("{soc")

    def test_literal_braces_are_supported(self) -> None:
        self.assertEqual(
            notifications.render_notification_template("{{SOC}} {soc}%", {"soc": 50}),
            "{SOC} 50%",
        )


if __name__ == "__main__":
    unittest.main()
