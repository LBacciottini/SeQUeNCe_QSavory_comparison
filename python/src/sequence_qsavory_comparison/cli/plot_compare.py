"""Create comparison CSV and plot artifacts from simulator summaries."""

from __future__ import annotations

import argparse
import pathlib

from sequence_qsavory_comparison.common.plotting import (
    plot_batch_curves,
    plot_sweep_curves,
    read_summary_rows,
    read_sweep_summary_rows,
    write_comparison_csv,
    write_sweep_comparison_csv,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True, help="Aggregate completion-time CSV path")
    parser.add_argument("--plot-dir", default=None, help="Directory for PNG plots; defaults to the CSV parent")
    parser.add_argument("--fidelity-field", default="flow2_mean_fidelity")
    parser.add_argument("--mode", choices=("batch", "sweep"), default="batch")
    args = parser.parse_args()

    plot_dir = pathlib.Path(args.plot_dir) if args.plot_dir else pathlib.Path(args.output).parent
    if args.mode == "sweep":
        rows = read_sweep_summary_rows(args.input)
        write_sweep_comparison_csv(rows, args.output, fidelity_field=args.fidelity_field)
        plot_sweep_curves(args.input, plot_dir, fidelity_field=args.fidelity_field)
    else:
        rows = read_summary_rows(args.input)
        write_comparison_csv(rows, args.output)
        plot_batch_curves(args.input, plot_dir, fidelity_field=args.fidelity_field)
