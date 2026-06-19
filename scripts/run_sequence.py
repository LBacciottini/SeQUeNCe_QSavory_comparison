#!/usr/bin/env python3
"""Run the SeQUeNCe adapter from a shared TOML config."""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.common.config import load_config
from src.sequence_impl.adapter import run_sequence


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.toml")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run_sequence(load_config(args.config), args.seed, args.output)


if __name__ == "__main__":
    main()
