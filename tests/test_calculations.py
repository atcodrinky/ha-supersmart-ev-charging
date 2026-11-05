"""Regression tests derived from Automazioni.yaml and Logica.xlsx."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


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
