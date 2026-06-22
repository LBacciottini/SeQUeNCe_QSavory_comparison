import unittest
import sys
import tempfile
import os
from unittest.mock import patch
from pathlib import Path

from sequence_qsavory_comparison.cli import run_batch
from sequence_qsavory_comparison.cli import run_sweep
from sequence_qsavory_comparison.common.config import load_config
from sequence_qsavory_comparison.cli.jobs import parse_worker_count


class BatchRunnerTests(unittest.TestCase):
    def test_qsavory_batch_schedules_exact_and_werner_variants(self):
        argv = [
            "run_batch.py",
            "--config",
            "shared/configs/default.toml",
            "--seeds",
            "7",
            "--output",
            "outputs/test_batch",
            "--simulators",
            "qsavory",
        ]
        with patch.object(sys, "argv", argv), patch("sequence_qsavory_comparison.cli.run_batch.run_jobs") as run:
            run_batch.main()

        jobs = run.call_args.args[0]
        commands = [job.command for job in jobs]
        self.assertEqual(len(commands), 2)
        self.assertIn("--raw-state-model", commands[0])
        self.assertIn("--raw-state-model", commands[1])
        self.assertEqual(commands[0][commands[0].index("--raw-state-model") + 1], "exact")
        self.assertEqual(commands[1][commands[1].index("--raw-state-model") + 1], "werner")
        self.assertIn("outputs/test_batch/qsavory_exact/seed_7", commands[0])
        self.assertIn("outputs/test_batch/qsavory_werner/seed_7", commands[1])
        self.assertIsNone(run.call_args.kwargs["prewarm_job"])

    def test_parallel_batch_uses_sequence_subprocess_and_julia_prewarm(self):
        argv = [
            "run_batch.py",
            "--config",
            "shared/configs/default.toml",
            "--seeds",
            "1",
            "--output",
            "outputs/test_batch",
            "--simulators",
            "sequence,qsavory",
            "--parallel",
        ]
        with (
            patch.object(sys, "argv", argv),
            patch("sequence_qsavory_comparison.cli.run_batch.run_jobs") as run,
            patch("sequence_qsavory_comparison.cli.run_batch.parse_worker_count", return_value=3) as parse,
        ):
            run_batch.main()

        jobs = run.call_args.args[0]
        self.assertEqual(parse.call_args.kwargs["parallel"], True)
        self.assertEqual(run.call_args.kwargs["workers"], 3)
        self.assertEqual(jobs[0].simulator, "sequence")
        self.assertEqual(jobs[0].command[0], sys.executable)
        self.assertEqual(run.call_args.kwargs["prewarm_job"].job_id, "julia_prewarm")


class SweepRunnerTests(unittest.TestCase):
    def test_parse_link_lengths_supports_defaults_and_ranges(self):
        self.assertEqual(run_sweep.DEFAULT_LINK_LENGTHS_KM, (5.0, 10.0, 20.0, 30.0, 40.0))
        self.assertEqual(run_sweep._parse_link_lengths("5,10,20"), [5.0, 10.0, 20.0])
        self.assertEqual(run_sweep._parse_link_lengths("5:15:5"), [5.0, 10.0, 15.0])
        self.assertEqual(parse_worker_count(None, parallel=True, job_count=100), max(1, min(100, (os.cpu_count() or 1) - 1)))

    def test_sweep_writes_generated_configs_and_qsavory_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "sweep"
            argv = [
                "run_sweep.py",
                "--config",
                "shared/configs/default.toml",
                "--link-lengths",
                "5,10",
                "--seeds",
                "7",
                "--output",
                str(out),
                "--simulators",
                "qsavory",
            ]
            with (
                patch.object(sys, "argv", argv),
                patch("sequence_qsavory_comparison.cli.run_sweep.run_jobs") as run,
            ):
                run_sweep.main()

            cfg5 = load_config(out / "link_005km" / "config.toml")
            cfg10 = load_config(out / "link_010km" / "config.toml")
            self.assertEqual(cfg5["topology"]["link_length_km"], 5.0)
            self.assertEqual(cfg10["topology"]["link_length_km"], 10.0)
            self.assertTrue((out / "sweep_manifest.json").is_file())

            jobs = run.call_args.args[0]
            commands = [job.command for job in jobs]
            self.assertEqual(len(commands), 4)
            self.assertIn(str(out / "link_005km" / "qsavory_exact" / "seed_7"), commands[0])
            self.assertIn(str(out / "link_005km" / "config.toml"), commands[0])
            self.assertIn(str(out / "link_010km" / "qsavory_werner" / "seed_7"), commands[3])
            self.assertEqual(run.call_args.kwargs["workers"], 1)
            self.assertIsNone(run.call_args.kwargs["prewarm_job"])

    def test_sweep_sequence_uses_generated_output_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "sweep"
            argv = [
                "run_sweep.py",
                "--config",
                "shared/configs/default.toml",
                "--link-lengths",
                "5",
                "--seeds",
                "1:2",
                "--output",
                str(out),
                "--simulators",
                "sequence",
            ]
            with (
                patch.object(sys, "argv", argv),
                patch("sequence_qsavory_comparison.cli.run_sweep.run_jobs") as run,
            ):
                run_sweep.main()

            jobs = run.call_args.args[0]
            self.assertEqual(len(jobs), 2)
            self.assertEqual(jobs[0].link_length_km, 5.0)
            self.assertEqual(jobs[0].command[0], sys.executable)
            self.assertEqual(jobs[0].output, str(out / "link_005km" / "sequence" / "seed_1"))
            self.assertEqual(jobs[1].output, str(out / "link_005km" / "sequence" / "seed_2"))

    def test_parallel_sweep_records_workers_and_prewarm(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "sweep"
            argv = [
                "run_sweep.py",
                "--config",
                "shared/configs/default.toml",
                "--link-lengths",
                "5",
                "--seeds",
                "1",
                "--output",
                str(out),
                "--simulators",
                "qsavory",
                "--workers",
                "2",
                "--parallel",
            ]
            with patch.object(sys, "argv", argv), patch("sequence_qsavory_comparison.cli.run_sweep.run_jobs") as run:
                run_sweep.main()

            self.assertEqual(run.call_args.kwargs["workers"], 2)
            self.assertEqual(run.call_args.kwargs["prewarm_job"].kind, "julia_prewarm")
            manifest = (out / "sweep_manifest.json").read_text(encoding="utf-8")
            self.assertIn('"workers": 2', manifest)
            self.assertIn('"julia_prewarm": true', manifest)


if __name__ == "__main__":
    unittest.main()
