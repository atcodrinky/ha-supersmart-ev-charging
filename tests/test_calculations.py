"""Regression tests derived from Automazioni.yaml and Logica.xlsx."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from datetime import datetime, timezone


MODULE = Path(__file__).parents[1] / "custom_components/supersmart_ev_charging/calculations.py"
SPEC = importlib.util.spec_from_file_location("supersmart_calculations", MODULE)
calculations = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(calculations)


class CalculationTests(unittest.TestCase):
    def test_pv_start_at_seven_amp_while_waiting(self) -> None:
        delta, target = calculations.pv_current_values(0, -1410, 200, 230)
        self.assertAlmostEqual(delta, 7.0)
        self.assertAlmostEqual(target, 7.0)

    def test_pv_modulation_keeps_current_already_delivered(self) -> None:
        delta, target = calculations.pv_current_values(1380, 0, 200, 230)
        self.assertAlmostEqual(delta, 0.869565, places=5)
        self.assertAlmostEqual(target, 6.869565, places=5)

    def test_negative_import_offset_keeps_an_export_margin(self) -> None:
        # With a -200 W offset, exporting 200 W is the neutral setpoint.
        delta, target = calculations.pv_current_values(1380, -200, -200, 230)
        self.assertEqual(delta, 0)
        self.assertEqual(target, 6)

        # If export falls to zero, the controller reduces current by ~0.87 A.
        delta, target = calculations.pv_current_values(1380, 0, -200, 230)
        self.assertAlmostEqual(delta, -0.869565, places=5)
        self.assertAlmostEqual(target, 5.130435, places=5)

    def test_wallbox_actual_current_uses_power_and_safe_voltage(self) -> None:
        self.assertEqual(calculations.wallbox_current_from_power(2300, 230), 10)
        self.assertEqual(calculations.wallbox_current_from_power(-1380, 0), 6)

    def test_pv_stop_threshold_uses_final_target(self) -> None:
        _, above_stop = calculations.pv_current_values(1380, 300, 200, 230)
        _, below_stop = calculations.pv_current_values(1380, 350, 200, 230)
        self.assertGreaterEqual(above_stop, 5.5)
        self.assertLess(below_stop, 5.5)

    def test_contract_balancing_excludes_wallbox_from_house_load(self) -> None:
        current = calculations.balanced_current(5700, 5000, 1380, 230, 25)
        self.assertEqual(current, 9.0)

    def test_force_and_night_balancing_can_reach_32_amp(self) -> None:
        current = calculations.balanced_current(22000, 1000, 0, 230, 32)
        self.assertEqual(current, 32.0)

    def test_voltage_fallback_and_clamp(self) -> None:
        self.assertEqual(calculations.clamp_voltage(0), 230)
        self.assertEqual(calculations.clamp_voltage(120), 180)
        self.assertEqual(calculations.clamp_voltage(280), 260)

    def test_active_soc_target_matches_each_charging_mode(self) -> None:
        args = {"force_charge": False, "solar_controller_active": False,
                "user_target": 50, "vehicle_target": 80}
        self.assertEqual(calculations.active_soc_target("night", **args), 50)
        self.assertEqual(calculations.active_soc_target("pv_surplus", **args), 80)
        self.assertEqual(calculations.active_soc_target("force", **args), 80)
        self.assertEqual(calculations.active_soc_target("scheduled_departure", **args), 80)
        self.assertEqual(
            calculations.active_soc_target(
                "idle", False, True, args["user_target"], args["vehicle_target"]
            ),
            80,
        )

    def test_charging_time_uses_configured_usable_capacity(self) -> None:
        # 60% of a 77 kWh usable battery is 46.2 kWh: at 7.7 kW = 6 hours.
        self.assertAlmostEqual(
            calculations.charging_time_minutes(20, 80, 77, 7700),
            360,
        )
        self.assertIsNone(
            calculations.charging_time_minutes(20, 80, 77, 100)
        )

    def test_missing_soc_only_allows_charging_when_explicitly_enabled(self) -> None:
        self.assertFalse(calculations.soc_below_target(0, False, 50, False))
        self.assertTrue(calculations.soc_below_target(0, False, 50, True))
        self.assertTrue(calculations.soc_below_target(40, True, 50, False))
        self.assertFalse(calculations.soc_below_target(50, True, 50, True))

    def test_missing_soc_never_reports_target_reached(self) -> None:
        self.assertFalse(calculations.soc_target_reached(100, False, 80))
        self.assertTrue(calculations.soc_target_reached(80, True, 80))

    def test_scheduled_departure_calculates_latest_safe_start(self) -> None:
        now = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)
        departure = datetime(2026, 11, 21, 6, 0, tzinfo=timezone.utc)
        plan = calculations.scheduled_departure_plan(
            now=now,
            departure_time=departure,
            current_soc=40,
            target_soc=80,
            usable_capacity_kwh=60,
            charging_efficiency_percent=100,
            available_power_w=6000,
            safety_margin_minutes=30,
        )
        self.assertEqual(plan.required_energy_kwh, 24)
        self.assertEqual(plan.required_minutes, 240)
        self.assertEqual(
            plan.scheduled_start,
            datetime(2026, 11, 21, 1, 30, tzinfo=timezone.utc),
        )

    def test_scheduled_departure_reports_delay(self) -> None:
        now = datetime(2026, 11, 20, 6, 0, tzinfo=timezone.utc)
        plan = calculations.scheduled_departure_plan(
            now=now,
            departure_time=datetime(2026, 11, 20, 7, 0, tzinfo=timezone.utc),
            current_soc=20,
            target_soc=80,
            usable_capacity_kwh=60,
            charging_efficiency_percent=100,
            available_power_w=6000,
            safety_margin_minutes=0,
        )
        self.assertEqual(plan.delay_minutes, 300)

    def test_moving_departure_forward_cancels_the_override(self) -> None:
        now = datetime(2026, 11, 22, 9, 0, tzinfo=timezone.utc)
        self.assertTrue(
            calculations.scheduled_departure_should_override(
                vehicle_connected=True,
                now=now,
                scheduled_start=datetime(
                    2026, 11, 22, 8, 0, tzinfo=timezone.utc
                ),
            )
        )
        self.assertFalse(
            calculations.scheduled_departure_should_override(
                vehicle_connected=True,
                now=now,
                scheduled_start=datetime(
                    2026, 11, 22, 15, 0, tzinfo=timezone.utc
                ),
            )
        )

    def test_active_departure_session_remains_locked(self) -> None:
        now = datetime(2026, 11, 22, 9, 0, tzinfo=timezone.utc)
        self.assertTrue(
            calculations.scheduled_departure_should_override(
                vehicle_connected=True,
                now=now,
                scheduled_start=datetime(
                    2026, 11, 22, 15, 0, tzinfo=timezone.utc
                ),
                active_session=True,
            )
        )

    def test_restart_without_soc_does_not_start_before_saved_time(self) -> None:
        now = datetime(2026, 11, 22, 9, 0, tzinfo=timezone.utc)
        self.assertFalse(
            calculations.scheduled_departure_should_override(
                vehicle_connected=True,
                now=now,
                scheduled_start=datetime(
                    2026, 11, 22, 15, 0, tzinfo=timezone.utc
                ),
                active_session=False,
            )
        )

    def test_departure_start_moves_earlier_immediately(self) -> None:
        now = datetime(2026, 11, 22, 9, 0, tzinfo=timezone.utc)
        result = calculations.stabilize_departure_start(
            current_start=datetime(2026, 11, 22, 15, 0, tzinfo=timezone.utc),
            candidate_start=datetime(2026, 11, 22, 14, 30, tzinfo=timezone.utc),
            later_candidate_since=None,
            now=now,
            later_stability_seconds=300,
        )
        self.assertEqual(
            result.scheduled_start,
            datetime(2026, 11, 22, 14, 30, tzinfo=timezone.utc),
        )
        self.assertIsNone(result.later_candidate_since)

    def test_departure_start_moves_later_only_after_five_stable_minutes(self) -> None:
        current = datetime(2026, 11, 22, 15, 0, tzinfo=timezone.utc)
        candidate = datetime(2026, 11, 22, 16, 0, tzinfo=timezone.utc)
        now = datetime(2026, 11, 22, 9, 0, tzinfo=timezone.utc)
        first = calculations.stabilize_departure_start(
            current_start=current,
            candidate_start=candidate,
            later_candidate_since=None,
            now=now,
            later_stability_seconds=300,
        )
        self.assertEqual(first.scheduled_start, current)
        almost = calculations.stabilize_departure_start(
            current_start=current,
            candidate_start=candidate,
            later_candidate_since=first.later_candidate_since,
            now=datetime(2026, 11, 22, 9, 4, 59, tzinfo=timezone.utc),
            later_stability_seconds=300,
        )
        self.assertEqual(almost.scheduled_start, current)
        stable = calculations.stabilize_departure_start(
            current_start=current,
            candidate_start=candidate,
            later_candidate_since=first.later_candidate_since,
            now=datetime(2026, 11, 22, 9, 5, tzinfo=timezone.utc),
            later_stability_seconds=300,
        )
        self.assertEqual(stable.scheduled_start, candidate)
        self.assertIsNone(stable.later_candidate_since)

    def test_departure_draft_must_be_in_the_future(self) -> None:
        now = datetime(2026, 11, 22, 9, 0, tzinfo=timezone.utc)
        self.assertFalse(calculations.departure_draft_is_valid(None, now))
        self.assertFalse(
            calculations.departure_draft_is_valid(
                datetime(2026, 11, 22, 8, 59, tzinfo=timezone.utc), now
            )
        )
        self.assertTrue(
            calculations.departure_draft_is_valid(
                datetime(2026, 11, 22, 19, 0, tzinfo=timezone.utc), now
            )
        )

    def test_night_session_stops_when_offpeak_period_ends(self) -> None:
        self.assertTrue(
            calculations.night_charge_should_stop(
                "night", True, False, False, False
            )
        )

    def test_tariff_change_does_not_stop_other_charging_modes(self) -> None:
        self.assertFalse(
            calculations.night_charge_should_stop(
                "force", True, False, True, False
            )
        )
        self.assertFalse(
            calculations.night_charge_should_stop(
                "pv_surplus", True, False, False, True
            )
        )
        self.assertFalse(
            calculations.night_charge_should_stop(
                "night", True, True, False, False
            )
        )


if __name__ == "__main__":
    unittest.main()
