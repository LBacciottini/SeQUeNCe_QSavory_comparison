#!/usr/bin/env python3
"""Root wrapper for the SeQUeNCe runner."""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PYTHON_SRC = ROOT / "python" / "src"
if str(PYTHON_SRC) not in sys.path:
    sys.path.insert(0, str(PYTHON_SRC))

from sequence_qsavory_comparison.cli.run_sequence import main


if __name__ == "__main__":
    main()
