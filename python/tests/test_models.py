import unittest
import math

from sequence_qsavory_comparison.common.config import load_config, resolve_config
from sequence_qsavory_comparison.common.models import barrett_kok_fidelity_symmetric, derive_parameters


class ModelFormulaTests(unittest.TestCase):
    def test_ideal_bk_fidelity_is_one(self):
        self.assertAlmostEqual(barrett_kok_fidelity_symmetric(1.0, 1.0, 1.0, 0.0), 1.0)

    def test_derived_bk_probability_uses_detector_efficiency(self):
        cfg = load_config("shared/configs/default.toml")
        derived = derive_parameters(cfg)
        expected = 0.5 * derived["detector_click_probability"] ** 2
        expected_source = (
            cfg["memories"]["emission_efficiency"]
            * cfg["optics"]["collection_efficiency"]
            * cfg["optics"]["frequency_conversion_efficiency"]
        )
        self.assertAlmostEqual(derived["barrett_kok_success_probability"], expected)
        self.assertAlmostEqual(derived["barrett_kok_full_success_probability"], expected)
        self.assertAlmostEqual(derived["source_transmissivity"], expected_source)
        self.assertAlmostEqual(derived["arm_transmissivity"], expected_source * derived["fiber_transmissivity_half_link"])

    def test_effective_attempt_time_accounts_for_short_circuit(self):
        cfg = load_config("shared/configs/default.toml")
        derived = derive_parameters(cfg)
        p_reaches_round2 = math.sqrt(derived["barrett_kok_full_success_probability"])
        expected = derived["barrett_kok_round1_time_s"] + p_reaches_round2 * derived["barrett_kok_round2_time_s"]

        self.assertAlmostEqual(derived["barrett_kok_round2_entry_probability"], p_reaches_round2)
        self.assertAlmostEqual(derived["barrett_kok_effective_attempt_time_s"], expected)
        self.assertEqual(derived["barrett_kok_resource_request_arrival_ps"], 50_000_000)
        self.assertEqual(derived["barrett_kok_protocol_start_nonprimary_ps"], 100_000_000)
        self.assertEqual(derived["barrett_kok_round1_min_emit_ps"], 150_000_000)
        self.assertEqual(derived["barrett_kok_round1_emit_ps"], 150_000_000)
        self.assertEqual(derived["barrett_kok_round1_failure_time_ps"], 225_000_010)
        self.assertEqual(derived["barrett_kok_round2_min_emit_ps"], 325_000_010)
        self.assertEqual(derived["barrett_kok_round2_emit_ps"], 325_012_500)
        self.assertEqual(derived["barrett_kok_two_round_time_ps"], 400_012_510)
        self.assertEqual(derived["barrett_kok_round2_increment_time_ps"], 175_012_500)
        self.assertAlmostEqual(derived["barrett_kok_round1_time_s"], 0.00022500001)
        self.assertAlmostEqual(derived["barrett_kok_round2_time_s"], 0.0001750125)
        self.assertAlmostEqual(derived["barrett_kok_two_round_time_s"], 0.00040001251)
        self.assertNotIn("attempt_time_s", derived)
        self.assertNotIn("attempt_cap_hz", derived)
        self.assertLess(derived["barrett_kok_effective_attempt_time_s"], 2.0 * derived["barrett_kok_round1_time_s"])
        self.assertAlmostEqual(
            derived["barrett_kok_expected_rate_hz"],
            derived["barrett_kok_full_success_probability"] / derived["barrett_kok_effective_attempt_time_s"],
        )

    def test_target_fidelity_policy(self):
        resolved = resolve_config(load_config("shared/configs/default.toml"))
        raw = resolved["derived"]["barrett_kok_raw_fidelity"]
        self.assertAlmostEqual(
            resolved["derived"]["target_purification_fidelity"],
            raw * raw + resolved["purification"]["target_fidelity_margin"],
        )


if __name__ == "__main__":
    unittest.main()
