"""Analyze diagnostic campaign outputs and identify the first divergence."""

from __future__ import annotations

import argparse
import pathlib
import sys

from sequence_qsavory_comparison.common.diagnostics import (
    compare_diagnostic_metrics,
    diagnostic_metric_rows,
    diagnostic_metric_rows_from_stage_summaries,
    first_divergence,
    read_diagnostic_events,
    read_diagnostic_stage_summaries,
    write_diagnostic_comparison_csv,
    write_root_cause_report,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Diagnostic campaign root")
    parser.add_argument("--output", required=True, help="Directory for diagnostic_comparison.csv and root_cause_report.md")
    parser.add_argument("--reference", default="sequence")
    parser.add_argument("--candidate", default="qsavory_exact")
    parser.add_argument("--minimum-relative-gap", type=float, default=0.05)
    parser.add_argument(
        "--source",
        choices=("stage-summary", "events"),
        default="stage-summary",
        help="Read compact stage summaries by default; use raw events only for low-level trace debugging.",
    )
    args = parser.parse_args()

    if args.source == "events":
        events = read_diagnostic_events(args.input)
        metrics = diagnostic_metric_rows(events)
    else:
        stages = read_diagnostic_stage_summaries(args.input)
        metrics = diagnostic_metric_rows_from_stage_summaries(stages)
    comparisons = compare_diagnostic_metrics(metrics, reference_simulator=args.reference, candidate_simulator=args.candidate)
    divergence = first_divergence(comparisons, minimum_relative_gap=args.minimum_relative_gap)

    out = pathlib.Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    write_diagnostic_comparison_csv(out / "diagnostic_comparison.csv", comparisons)
    write_root_cause_report(out / "root_cause_report.md", comparisons, divergence)
    if divergence is None:
        print("No first divergence found with the configured criterion.")
    else:
        print(f"First divergence: {divergence['scenario']} / {divergence['stage']} / {divergence['event']}")


def run() -> None:
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
