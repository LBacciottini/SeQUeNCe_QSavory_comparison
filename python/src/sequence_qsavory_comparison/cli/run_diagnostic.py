"""Run one diagnostic scenario for SeQUeNCe or QuantumSavory."""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

from sequence_qsavory_comparison.common.config import load_config
from sequence_qsavory_comparison.common.diagnostics import SCENARIOS
from sequence_qsavory_comparison.sequence.diagnostics import run_sequence_diagnostic

from .run_batch import _julia_project, _repo_root


def _run_qsavory(root: pathlib.Path, args: argparse.Namespace) -> None:
    command = [
        "julia",
        f"--project={_julia_project(root)}",
        str(root / "scripts" / "run_qsavory_diagnostic.jl"),
        "--config",
        args.config,
        "--seed",
        str(args.seed),
        "--scenario",
        args.scenario,
        "--raw-state-model",
        args.raw_state_model,
        "--output",
        args.output,
    ]
    subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="shared/configs/default.toml")
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--scenario", required=True, choices=SCENARIOS)
    parser.add_argument("--simulator", required=True, choices=("sequence", "qsavory"))
    parser.add_argument("--raw-state-model", default="exact", choices=("exact", "werner"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if args.simulator == "sequence":
        run_sequence_diagnostic(load_config(args.config), seed=args.seed, scenario=args.scenario, output_dir=args.output)
    else:
        _run_qsavory(_repo_root(), args)


def run() -> None:
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
