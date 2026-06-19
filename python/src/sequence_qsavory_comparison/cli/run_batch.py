"""Run one or both simulators for a range of seeds."""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

from sequence_qsavory_comparison.common.config import load_config
from sequence_qsavory_comparison.sequence import run_sequence

QSAVORY_RAW_STATE_MODELS = ("exact", "werner")


def _repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[4]


def _parse_seeds(spec: str) -> list[int]:
    if ":" in spec:
        start, stop = [int(part) for part in spec.split(":", 1)]
        return list(range(start, stop + 1))
    return [int(part) for part in spec.split(",") if part]


def _parse_simulators(spec: str) -> set[str]:
    return {item.strip() for item in spec.split(",") if item.strip()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="shared/configs/default.toml")
    parser.add_argument("--seeds", required=True, help="Comma list or inclusive start:stop range")
    parser.add_argument("--output", required=True)
    parser.add_argument("--simulators", default="sequence,qsavory")
    args = parser.parse_args()

    config = load_config(args.config)
    out_root = pathlib.Path(args.output)
    simulators = _parse_simulators(args.simulators)
    root = _repo_root()
    julia_project = root / "julia" / "SeQUeNCeQSavoryComparison"

    for seed in _parse_seeds(args.seeds):
        if "sequence" in simulators:
            run_sequence(config, seed, out_root / "sequence" / f"seed_{seed}")
        if "qsavory" in simulators:
            for raw_state_model in QSAVORY_RAW_STATE_MODELS:
                subprocess.run(
                    [
                        "julia",
                        f"--project={julia_project}",
                        str(root / "scripts" / "run_qsavory.jl"),
                        "--config",
                        args.config,
                        "--seed",
                        str(seed),
                        "--raw-state-model",
                        raw_state_model,
                        "--output",
                        str(out_root / f"qsavory_{raw_state_model}" / f"seed_{seed}"),
                    ],
                    check=True,
                )


def run() -> None:
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
