import copy
import unittest

from src.common.config import load_config, resolve_config, validate_config


class CommonConfigTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config("configs/default.toml")

    def test_default_config_resolves_derived_parameters(self):
        resolved = resolve_config(self.config)
        derived = resolved["derived"]
        self.assertAlmostEqual(derived["half_link_km"], 5.0)
        self.assertGreater(derived["arm_transmissivity"], 0.0)
        self.assertLess(derived["arm_transmissivity"], 1.0)
        self.assertGreater(derived["barrett_kok_success_probability"], 0.0)
        self.assertLess(derived["barrett_kok_success_probability"], 1.0)
        self.assertGreater(derived["barrett_kok_effective_attempt_time_s"], derived["barrett_kok_round1_time_s"])
        self.assertLess(derived["barrett_kok_effective_attempt_time_s"], 2.0 * derived["barrett_kok_round1_time_s"])

    def test_rejects_overlapping_reservations(self):
        bad = copy.deepcopy(self.config)
        bad["resource_reservation"]["flow2"]["r1_slots"] = [5, 14]
        with self.assertRaises(ValueError):
            validate_config(bad)

    def test_rejects_invalid_probability(self):
        bad = copy.deepcopy(self.config)
        bad["detectors"]["efficiency"] = 1.5
        with self.assertRaises(ValueError):
            validate_config(bad)

    def test_rejects_swap_degradation(self):
        bad = copy.deepcopy(self.config)
        bad["swapping"]["degradation"] = 0.95
        with self.assertRaisesRegex(ValueError, "swapping.degradation"):
            validate_config(bad)

    def test_rejects_mismatched_lane_counts(self):
        bad = copy.deepcopy(self.config)
        bad["resource_reservation"]["flow2"]["r3_slots"] = [0, 8]
        with self.assertRaisesRegex(ValueError, "same lane count"):
            validate_config(bad)


if __name__ == "__main__":
    unittest.main()
