import csv
import json
import pathlib
import tempfile
import unittest

from sequence_qsavory_comparison.common.config import load_config
from sequence_qsavory_comparison.common.diagnostics import (
    DiagnosticRecorder,
    compare_diagnostic_metrics,
    diagnostic_metric_rows,
    diagnostic_metric_rows_from_stage_summaries,
    first_divergence,
    read_diagnostic_events,
    read_diagnostic_stage_summaries,
    scenario_config,
    summarize_events,
    write_diagnostic_comparison_csv,
    write_root_cause_report,
)
from sequence_qsavory_comparison.common.outputs import DIAGNOSTIC_EVENT_FIELDS, DIAGNOSTIC_STAGE_FIELDS, write_diagnostic_events_csv, write_diagnostic_stage_csv
from sequence_qsavory_comparison.sequence.adapter import _import_sequence
from sequence_qsavory_comparison.sequence.diagnostics import run_sequence_diagnostic


def _sequence_is_available() -> bool:
    cfg = load_config("shared/configs/default.toml")
    try:
        _import_sequence(cfg["paths"].get("sequence_path"))
    except ModuleNotFoundError:
        return False
    return True


class DiagnosticHelperTests(unittest.TestCase):
    def test_scenario_config_overlays_isolate_layers(self):
        cfg = load_config("shared/configs/default.toml")

        single = scenario_config(cfg, "single_lane_elementary")
        self.assertEqual(single["resource_reservation"]["flow1"]["r1_slots"], [0, 0])
        self.assertEqual(single["resource_reservation"]["flow2"]["target_pairs"], 0)
        self.assertFalse(single["purification"]["enabled"])

        swap_only = scenario_config(cfg, "eg_swap_no_purification")
        self.assertEqual(swap_only["resource_reservation"]["flow1"]["target_pairs"], 0)
        self.assertGreater(swap_only["resource_reservation"]["flow2"]["target_pairs"], 0)
        self.assertFalse(swap_only["purification"]["enabled"])

        reduced = scenario_config(cfg, "full_reduced")
        self.assertEqual(reduced["resource_reservation"]["flow2"]["target_pairs"], 2)
        self.assertTrue(reduced["purification"]["enabled"])

    def test_event_and_stage_schema_are_stable(self):
        recorder = DiagnosticRecorder("sequence", 7, "same_link_multilane", 10.0)
        recorder.log(stage="barrett_kok", event="success", time_s=0.1, flow="flow1", link="r1-r2", node="r1", slot=0)
        recorder.log(stage="barrett_kok", event="success", time_s=0.3, flow="flow1", link="r1-r2", node="r1", slot=1)
        stages = summarize_events(recorder.events)

        with tempfile.TemporaryDirectory() as tmpdir:
            events_path = f"{tmpdir}/events.csv"
            stages_path = f"{tmpdir}/stage_summary.csv"
            write_diagnostic_events_csv(events_path, recorder.events)
            write_diagnostic_stage_csv(stages_path, stages)
            with open(events_path, newline="", encoding="utf-8") as handle:
                self.assertEqual(next(csv.reader(handle)), list(DIAGNOSTIC_EVENT_FIELDS))
            with open(stages_path, newline="", encoding="utf-8") as handle:
                self.assertEqual(next(csv.reader(handle)), list(DIAGNOSTIC_STAGE_FIELDS))
        self.assertEqual(stages[0]["count"], 2)
        self.assertAlmostEqual(stages[0]["mean_interarrival_s"], 0.2)

    def test_analyzer_finds_first_divergent_stage(self):
        rows = []
        for seed in (1, 2, 3):
            rows.extend(
                [
                    {"simulator": "sequence", "seed": seed, "scenario": "same_link_multilane", "stage": "elementary_delivered", "event": "delivered", "time_s": 1.0 + seed * 0.01},
                    {"simulator": "qsavory_exact", "seed": seed, "scenario": "same_link_multilane", "stage": "elementary_delivered", "event": "delivered", "time_s": 1.0 + seed * 0.01},
                    {"simulator": "sequence", "seed": seed, "scenario": "eg_swap_no_purification", "stage": "swapped_delivered", "event": "delivered", "time_s": 2.0 + seed * 0.01},
                    {"simulator": "qsavory_exact", "seed": seed, "scenario": "eg_swap_no_purification", "stage": "swapped_delivered", "event": "delivered", "time_s": 1.0 + seed * 0.01},
                ]
            )
        metrics = diagnostic_metric_rows(rows)
        comparisons = compare_diagnostic_metrics(metrics)
        divergence = first_divergence(comparisons, minimum_relative_gap=0.05)
        self.assertIsNotNone(divergence)
        assert divergence is not None
        self.assertEqual(divergence["scenario"], "eg_swap_no_purification")
        self.assertEqual(divergence["stage"], "swapped_delivered")

        with tempfile.TemporaryDirectory() as tmpdir:
            comparison_path = pathlib.Path(tmpdir) / "diagnostic_comparison.csv"
            report_path = pathlib.Path(tmpdir) / "root_cause_report.md"
            write_diagnostic_comparison_csv(comparison_path, comparisons)
            write_root_cause_report(report_path, comparisons, divergence)
            self.assertIn("First Divergence", report_path.read_text(encoding="utf-8"))

    def test_read_diagnostic_events_scans_campaign_layout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = pathlib.Path(tmpdir) / "same_link_multilane" / "sequence" / "seed_1"
            run_dir.mkdir(parents=True)
            write_diagnostic_events_csv(
                run_dir / "events.csv",
                [{"simulator": "sequence", "seed": 1, "scenario": "same_link_multilane", "stage": "elementary_delivered", "event": "delivered", "time_s": 1.0}],
            )
            rows = read_diagnostic_events(tmpdir)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["stage"], "elementary_delivered")

    def test_stage_summary_metrics_avoid_raw_event_scan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for simulator, time_s, count in (("sequence", 2.0, 10), ("qsavory_exact", 1.0, 8)):
                run_dir = pathlib.Path(tmpdir) / "eg_swap_no_purification" / simulator / "seed_1"
                run_dir.mkdir(parents=True)
                write_diagnostic_stage_csv(
                    run_dir / "stage_summary.csv",
                    [
                        {
                            "simulator": simulator,
                            "seed": 1,
                            "scenario": "eg_swap_no_purification",
                            "link_length_km": 10.0,
                            "stage": "swapped_delivered",
                            "event": "delivered",
                            "count": count,
                            "first_time_s": 0.1,
                            "nth_time_s": time_s,
                            "mean_interarrival_s": "",
                            "mean_duration_s": "",
                        }
                    ],
                )
            rows = read_diagnostic_stage_summaries(tmpdir)
            metrics = diagnostic_metric_rows_from_stage_summaries(rows)
            comparisons = compare_diagnostic_metrics(metrics)
            divergence = first_divergence(comparisons, minimum_relative_gap=0.05)
            self.assertIsNotNone(divergence)
            assert divergence is not None
            self.assertFalse(divergence["event_counts_match"])
            self.assertEqual(divergence["stage"], "swapped_delivered")


@unittest.skipUnless(_sequence_is_available(), "SeQUeNCe is not installed in this Python environment")
class SequenceDiagnosticSmokeTests(unittest.TestCase):
    def test_sequence_diagnostic_writes_outputs(self):
        cfg = load_config("shared/configs/default.toml")
        cfg["experiment"]["runtime_s"] = 1.0e-6
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_sequence_diagnostic(cfg, seed=5, scenario="single_lane_elementary", output_dir=tmpdir)
            self.assertIn("events", result)
            with open(f"{tmpdir}/diagnostic_manifest.json", encoding="utf-8") as handle:
                manifest = json.load(handle)
            self.assertEqual(manifest["scenario"], "single_lane_elementary")
            self.assertEqual(manifest["simulator"], "sequence")


if __name__ == "__main__":
    unittest.main()
