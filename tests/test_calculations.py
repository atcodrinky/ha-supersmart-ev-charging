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


if __name__ == "__main__":
    unittest.main()
