import copy
import csv
import json
import pathlib
import tempfile
import unittest

from sequence_qsavory_comparison.common.config import load_config
from sequence_qsavory_comparison.sequence.adapter import _import_sequence, run_sequence


def _sequence_is_available() -> bool:
    """Return true when the current Python environment can import SeQUeNCe."""

    cfg = load_config("shared/configs/default.toml")
    try:
        _import_sequence(cfg["paths"].get("sequence_path"))
    except ModuleNotFoundError:
        return False
    return True


@unittest.skipUnless(_sequence_is_available(), "SeQUeNCe is not installed in this Python environment")
class SequenceIntegrationTests(unittest.TestCase):
    def test_sequence_runner_writes_canonical_outputs(self):
        cfg = copy.deepcopy(load_config("shared/configs/default.toml"))
        cfg["experiment"]["runtime_s"] = 1.0e-6
        cfg["experiment"]["seed_count"] = 1

        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_sequence(cfg, seed=11, output_dir=tmpdir)
            out = pathlib.Path(tmpdir)

            manifest_path = out / cfg["outputs"]["manifest_filename"]
            summary_path = out / cfg["outputs"]["summary_filename"]
            pairs_path = out / cfg["outputs"]["pairs_filename"]

            self.assertTrue(manifest_path.exists())
            self.assertTrue(summary_path.exists())
            self.assertTrue(pairs_path.exists())
            self.assertEqual(result["summary"]["simulator"], "sequence")
            self.assertEqual(result["summary"]["seed"], 11)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["simulator"], "sequence")
            self.assertEqual(manifest["seed"], 11)
            self.assertEqual(manifest["resolved_config"]["experiment"]["runtime_s"], 1.0e-6)
            self.assertEqual(manifest["applied_config"]["memory_counts"]["r2"], cfg["memories"]["r2_count"])
            self.assertEqual(
                manifest["applied_config"]["rules"]["flow2_r2_right_slots"],
                cfg["resource_reservation"]["flow2"]["r2_right_slots"],
            )

            with summary_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["simulator"], "sequence")
            self.assertEqual(rows[0]["seed"], "11")


if __name__ == "__main__":
    unittest.main()
