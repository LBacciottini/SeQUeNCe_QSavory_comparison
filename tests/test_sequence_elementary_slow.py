import os
import unittest

from src.common.config import load_config
from src.common.validation import assert_mean_completion_time, elementary_rate_theory
from src.sequence_impl.adapter import _import_sequence
from src.sequence_impl.elementary import run_sequence_elementary_trials


def _sequence_is_available() -> bool:
    cfg = load_config("configs/default.toml")
    try:
        _import_sequence(cfg["paths"].get("sequence_path"))
    except ModuleNotFoundError:
        return False
    return True


@unittest.skipUnless(os.environ.get("RUN_SLOW_SIM_TESTS") == "1", "set RUN_SLOW_SIM_TESTS=1 to run slow statistical tests")
@unittest.skipUnless(_sequence_is_available(), "SeQUeNCe is not installed in this Python environment")
class SequenceElementarySlowTests(unittest.TestCase):
    def test_elementary_generation_rate_and_fidelity_match_theory(self):
        cfg = load_config("configs/default.toml")
        trials = int(os.environ.get("ELEMENTARY_TEST_TRIALS", "300"))
        theory = elementary_rate_theory(cfg)
        timeout_s = float(os.environ.get("ELEMENTARY_TEST_TIMEOUT_S", str(20.0 / theory["expected_rate_hz"])))

        rows = run_sequence_elementary_trials(cfg, seed=101, trials=trials, timeout_s=timeout_s)
        successes = [row for row in rows if row["success"]]

        self.assertEqual(len(successes), trials, "every first-success trial should finish before the safety timeout")
        completion_times = [float(row["completion_time_s"]) for row in successes]
        assert_mean_completion_time(
            "sequence elementary mean completion time",
            completion_times,
            theory["expected_mean_completion_time_s"],
        )
        for row in successes:
            self.assertAlmostEqual(float(row["fidelity"]), theory["expected_raw_fidelity"], places=12)


if __name__ == "__main__":
    unittest.main()
