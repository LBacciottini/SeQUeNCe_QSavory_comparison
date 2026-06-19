#!/usr/bin/env python3
"""Create comparison CSV and plot artifacts from simulator summaries."""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.common.plotting import plot_batch_curves, read_summary_rows, write_comparison_csv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True, help="Aggregate completion-time CSV path")
    parser.add_argument("--plot-dir", default=None, help="Directory for PNG plots; defaults to the CSV parent")
    parser.add_argument("--fidelity-field", default="flow2_mean_fidelity")
    args = parser.parse_args()

    rows = read_summary_rows(args.input)
    write_comparison_csv(rows, args.output)
    plot_dir = pathlib.Path(args.plot_dir) if args.plot_dir else pathlib.Path(args.output).parent
    plot_batch_curves(args.input, plot_dir, fidelity_field=args.fidelity_field)


if __name__ == "__main__":
    main()
