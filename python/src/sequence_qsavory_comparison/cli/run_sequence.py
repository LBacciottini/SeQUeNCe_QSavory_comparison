"""Run the SeQUeNCe adapter from a shared TOML config.

This module is the small command-line wrapper around
``sequence_qsavory_comparison.sequence.run_sequence``.  It is used directly by
the batch and sweep job scheduler so each SeQUeNCe seed runs in its own Python
process and writes a self-contained canonical output directory.
"""

from __future__ import annotations

import argparse

from sequence_qsavory_comparison.common.config import load_config
from sequence_qsavory_comparison.sequence import run_sequence


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="shared/configs/default.toml")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run_sequence(load_config(args.config), args.seed, args.output)
