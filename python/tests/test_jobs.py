import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sequence_qsavory_comparison.cli.jobs import Job, JobFailure, run_jobs


class JobRunnerTests(unittest.TestCase):
    def test_fail_fast_terminates_running_and_cancels_pending_jobs(self):
        jobs = [
            Job("fail", "simulation", "sequence", ["fail"]),
            Job("running", "simulation", "qsavory_exact", ["running"]),
            Job("pending", "simulation", "qsavory_werner", ["pending"]),
        ]
        processes = [_FakeProcess(1), _FakeProcess(None)]

        def popen(_command):
            return processes.pop(0)

        with tempfile.TemporaryDirectory() as tmp:
            with patch("sequence_qsavory_comparison.cli.jobs.subprocess.Popen", side_effect=popen):
                with self.assertRaises(JobFailure):
                    run_jobs(jobs, jobs_csv=Path(tmp) / "jobs.csv", workers=2)

            text = (Path(tmp) / "jobs.csv").read_text(encoding="utf-8")
            self.assertIn("fail,simulation,sequence", text)
            self.assertIn("failed,1", text)
            self.assertIn("running,simulation,qsavory_exact", text)
            self.assertIn("terminated,-15", text)
            self.assertIn("pending,simulation,qsavory_werner", text)
            self.assertIn("cancelled", text)


class _FakeProcess:
    def __init__(self, returncode):
        self._returncode = returncode
        self._terminated = False

    def poll(self):
        if self._terminated:
            return -15
        return self._returncode

    def wait(self):
        if self._terminated:
            return -15
        return self._returncode if self._returncode is not None else 0

    def terminate(self):
        self._terminated = True


if __name__ == "__main__":
    unittest.main()
