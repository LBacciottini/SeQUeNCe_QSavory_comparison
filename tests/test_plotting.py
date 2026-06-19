import csv
import tempfile
import unittest
from pathlib import Path

from src.common.plotting import read_summary_rows, series_by_simulator, write_comparison_csv


class PlottingApiTests(unittest.TestCase):
    def test_reads_nested_summaries_and_groups_numeric_series(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for simulator, seed, completion, fidelity in (
                ("sequence", 1, "0.3", "0.91"),
                ("qsavory_exact", 1, "0.2", "0.93"),
                ("qsavory_werner", 1, "", "0.92"),
                ("sequence", 2, "0.4", ""),
            ):
                out = root / simulator / f"seed_{seed}"
                out.mkdir(parents=True)
                with (out / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(
                        handle,
                        fieldnames=[
                            "simulator",
                            "seed",
                            "status",
                            "runtime_s",
                            "completion_time_s",
                            "target_pairs",
                            "target_completed",
                            "flow1_delivered",
                            "flow2_delivered",
                            "flow1_mean_fidelity",
                            "flow2_mean_fidelity",
                        ],
                    )
                    writer.writeheader()
                    writer.writerow(
                        {
                            "simulator": simulator,
                            "seed": seed,
                            "status": "completed",
                            "runtime_s": "10",
                            "completion_time_s": completion,
                            "target_pairs": "10",
                            "target_completed": "true" if completion else "false",
                            "flow1_delivered": "10",
                            "flow2_delivered": "10",
                            "flow1_mean_fidelity": fidelity,
                            "flow2_mean_fidelity": fidelity,
                        }
                    )

            rows = read_summary_rows(root)
            completion_series = series_by_simulator(rows, "completion_time_s")
            fidelity_series = series_by_simulator(rows, "flow2_mean_fidelity")

            self.assertEqual(completion_series["sequence"], [(1, 0.3), (2, 0.4)])
            self.assertEqual(completion_series["qsavory_exact"], [(1, 0.2)])
            self.assertNotIn("qsavory_werner", completion_series)
            self.assertEqual(fidelity_series["qsavory_werner"], [(1, 0.92)])

            comparison = root / "comparison.csv"
            write_comparison_csv(rows, comparison)
            text = comparison.read_text(encoding="utf-8")
            self.assertIn("sequence,2,2,0.35", text)
            self.assertIn("qsavory_exact,1,1,0.2", text)


if __name__ == "__main__":
    unittest.main()
