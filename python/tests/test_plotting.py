import csv
import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from sequence_qsavory_comparison.common.plotting import (
    DEFAULT_SIMULATOR_ORDER,
    plot_sweep_curves,
    read_summary_rows,
    read_sweep_summary_rows,
    series_by_simulator,
    sweep_series_by_simulator,
    write_comparison_csv,
    write_sweep_comparison_csv,
    _series_style,
)


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

    def test_sweep_rows_are_enriched_and_aggregated_by_link_length(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for link_length, simulator, seed, completion, fidelity in (
                (5.0, "sequence", 1, "0.3", "0.91"),
                (5.0, "sequence", 2, "0.5", "0.93"),
                (5.0, "qsavory_exact", 1, "", "0.94"),
                (10.0, "sequence", 1, "0.8", "0.89"),
            ):
                out = root / f"link_{int(link_length):03d}km" / simulator / f"seed_{seed}"
                out.mkdir(parents=True)
                with (out / "manifest.json").open("w", encoding="utf-8") as handle:
                    json.dump({"resolved_config": {"topology": {"link_length_km": link_length}}}, handle)
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

            rows = read_sweep_summary_rows(root)
            self.assertEqual(len(rows), 4)
            self.assertEqual(rows[0]["link_length_km"], "5.0")
            completion_series = sweep_series_by_simulator(rows, "completion_time_s")
            fidelity_series = sweep_series_by_simulator(rows, "flow2_mean_fidelity")

            self.assertEqual(completion_series["sequence"][0][0], 5.0)
            self.assertAlmostEqual(completion_series["sequence"][0][1], 0.4)
            self.assertEqual(fidelity_series["qsavory_exact"], [(5.0, 0.94, 0.0)])

            comparison = root / "sweep_comparison.csv"
            write_sweep_comparison_csv(rows, comparison)
            text = comparison.read_text(encoding="utf-8")
            self.assertIn("link_length_km,simulator,runs,target_completed_runs", text)
            self.assertIn("5,sequence,2,2,2,0.4", text)
            self.assertIn("5,qsavory_exact,1,0,0,", text)

    def test_sweep_plot_api_returns_expected_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with unittest.mock.patch("sequence_qsavory_comparison.common.plotting._plot_errorbar_series") as plot:
                paths = plot_sweep_curves(root, root / "plots")

            self.assertEqual(plot.call_count, 2)
            self.assertEqual(paths["completion_time"], root / "plots" / "completion_time_by_link_length.pdf")
            self.assertEqual(paths["average_fidelity"], root / "plots" / "average_fidelity_by_link_length.pdf")

    def test_default_simulator_styles_use_distinct_markers(self):
        markers = [_series_style(index)["marker"] for index, _simulator in enumerate(DEFAULT_SIMULATOR_ORDER)]

        self.assertEqual(len(markers), len(set(markers)))


if __name__ == "__main__":
    unittest.main()
