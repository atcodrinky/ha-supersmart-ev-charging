"""Tests for Companion App Live Activity payload helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import types
import unittest


PACKAGE = Path(__file__).parents[1] / "custom_components/supersmart_ev_charging"
package = types.ModuleType("supersmart_ev_charging")
package.__path__ = [str(PACKAGE)]
sys.modules.setdefault("supersmart_ev_charging", package)

spec = importlib.util.spec_from_file_location(
    "supersmart_ev_charging.live_activity", PACKAGE / "live_activity.py"
)
live_activity = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = live_activity
assert spec.loader is not None
spec.loader.exec_module(live_activity)


class LiveActivityTests(unittest.TestCase):
    def test_soc_bucket_handles_jumps_and_bounds(self) -> None:
        self.assertEqual(live_activity.soc_bucket(44, 5), 40)
        self.assertEqual(live_activity.soc_bucket(51, 5), 50)
        self.assertEqual(live_activity.soc_bucket(110, 5), 100)

    def test_payload_uses_instance_title_progress_timer_and_url(self) -> None:
        payload = live_activity.build_live_payload(
            title="Škoda Elroq",
            message="Notturna F3 · 2.7 kW · target 80%",
            tag="supersmart_ev_entry",
            soc=45,
            target=80,
            mode="notturna_f3",
            remaining_minutes=135,
            dashboard_url="/lovelace/auto",
            silent=True,
        )
        self.assertEqual(payload["title"], "Škoda Elroq")
        self.assertEqual(payload["data"]["progress"], 45)
        self.assertEqual(payload["data"]["progress_max"], 100)
        self.assertEqual(payload["data"]["critical_text"], "🔋 45%")
        self.assertEqual(payload["data"]["when"], 8100)
        self.assertEqual(payload["data"]["url"], "/lovelace/auto")
        self.assertTrue(payload["data"]["live_update"])
        self.assertTrue(payload["data"]["silent"])

    def test_stale_soc_omits_progress_and_timer(self) -> None:
        payload = live_activity.build_live_payload(
            title="Tesla Model 3",
            message="SOC not updated",
            tag="supersmart_ev_entry",
            soc=None,
            target=80,
            mode="sconosciuta",
            remaining_minutes=None,
            dashboard_url="",
            silent=False,
        )
        self.assertNotIn("progress", payload["data"])
        self.assertNotIn("chronometer", payload["data"])
        self.assertNotIn("silent", payload["data"])

    def test_end_time_threshold(self) -> None:
        initial = datetime(2026, 9, 13, 12, tzinfo=timezone.utc)
        self.assertFalse(
            live_activity.end_time_shifted(
                initial, initial + timedelta(minutes=14), 15
            )
        )
        self.assertTrue(
            live_activity.end_time_shifted(
                initial, initial + timedelta(minutes=15), 15
            )
        )

    def test_tag_is_stable_and_within_companion_limit(self) -> None:
        tag = live_activity.live_activity_tag("x" * 100)
        self.assertEqual(tag, live_activity.live_activity_tag("x" * 100))
        self.assertLessEqual(len(tag), 64)


if __name__ == "__main__":
    unittest.main()
