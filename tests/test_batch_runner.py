import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_batch


class BatchRunnerTests(unittest.TestCase):
    def test_qsavory_batch_schedules_exact_and_werner_variants(self):
        argv = [
            "run_batch.py",
            "--config",
            "configs/default.toml",
            "--seeds",
            "7",
            "--output",
            "outputs/test_batch",
            "--simulators",
            "qsavory",
        ]
        with patch.object(sys, "argv", argv), patch("scripts.run_batch.subprocess.run") as run:
            run_batch.main()

        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(len(commands), 2)
        self.assertIn("--raw-state-model", commands[0])
        self.assertIn("--raw-state-model", commands[1])
        self.assertEqual(commands[0][commands[0].index("--raw-state-model") + 1], "exact")
        self.assertEqual(commands[1][commands[1].index("--raw-state-model") + 1], "werner")
        self.assertIn("outputs/test_batch/qsavory_exact/seed_7", commands[0])
        self.assertIn("outputs/test_batch/qsavory_werner/seed_7", commands[1])


if __name__ == "__main__":
    unittest.main()
