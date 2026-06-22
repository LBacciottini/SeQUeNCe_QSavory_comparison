"""Elementary-link validation harness for SeQUeNCe.

This module intentionally avoids purification, swapping, and multi-flow
resource management. It runs repeated one-link Barrett-Kok trials so slow tests
can compare raw generation rate and fidelity to shared theory.
"""

from __future__ import annotations

import copy
import pathlib
from typing import Any

from sequence_qsavory_comparison.common.config import resolve_config
from sequence_qsavory_comparison.common.outputs import ensure_output_dir
from sequence_qsavory_comparison.common.validation import elementary_rate_theory
from sequence_qsavory_comparison.sequence.generation import _install_eg_rule
from sequence_qsavory_comparison.sequence.imports import _import_sequence
from sequence_qsavory_comparison.sequence.network import _build_network


def _trial_config(config: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    trial = copy.deepcopy(config)
    trial["experiment"]["runtime_s"] = timeout_s
    return trial


def run_sequence_elementary_trials(
    config: dict[str, Any],
    *,
    seed: int,
    trials: int,
    timeout_s: float,
    output_dir: str | pathlib.Path | None = None,
) -> list[dict[str, Any]]:
    """Run independent first-success elementary Barrett-Kok trials.

    Each trial builds a fresh one-link SeQUeNCe network with a single reserved
    memory pair and runs until the first successful Barrett-Kok generation or
    the trial timeout.  The function reuses the production SeQUeNCe generation
    rule actions, so validation exercises the same protocol wiring as full
    comparison runs while excluding purification and swapping.

    Args:
        config: Shared configuration dictionary.
        seed: Base seed.  Each trial receives a deterministic offset from this
            value so trials are reproducible and independent.
        trials: Number of independent first-success experiments to run.
        timeout_s: Maximum simulated time for each trial, in seconds.
        output_dir: Optional directory where ``elementary_trials.csv`` is
            written.

    Returns:
        A list of row dictionaries with observed success, completion time,
        fidelity, and the corresponding theoretical rate/fidelity columns.

    Example:
        >>> rows = run_sequence_elementary_trials(cfg, seed=1, trials=10, timeout_s=1.0)  # doctest: +SKIP
        >>> rows[0].get("simulator")  # doctest: +SKIP
        'sequence'
    """

    trial_config = _trial_config(config, timeout_s)
    resolved = resolve_config(trial_config)
    imports = _import_sequence(resolved["paths"].get("sequence_path"))
    theory = elementary_rate_theory(config)
    rows: list[dict[str, Any]] = []

    for trial_index in range(1, trials + 1):
        timeline, r1, r2, _r3 = _build_network(resolved, imports, seed + trial_index * 1009)
        timeline.init()
        _install_eg_rule(imports.Rule, r1, _eg_action_request, "m12", "r2", [0, 0], "r1", [0, 0])
        _install_eg_rule(imports.Rule, r2, _eg_action_await, "m12", "r1", [0, 0])
        timeline.run()

        info = r1.resource_manager.memory_manager[0]
        success = info.state == "ENTANGLED" and info.entangle_time > 0
        rows.append(
            {
                "simulator": "sequence",
                "seed": seed,
                "trial": trial_index,
                "success": success,
                "completion_time_s": info.entangle_time * 1e-12 if success else "",
                "timeout_s": timeout_s,
                "effective_attempt_time_s": theory["effective_attempt_time_s"],
                "success_probability": theory["attempt_success_probability"],
                "round2_entry_probability": theory["round2_entry_probability"],
                "round1_time_s": theory["round1_time_s"],
                "round2_time_s": theory["round2_time_s"],
                "expected_rate_hz": theory["expected_rate_hz"],
                "fidelity": float(info.fidelity) if success else "",
                "expected_fidelity": theory["expected_raw_fidelity"],
            }
        )

    if output_dir is not None:
        out = ensure_output_dir(output_dir)
        _write_validation_csv(out / "elementary_trials.csv", rows)
    return rows


def _write_validation_csv(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    fields = (
        "simulator",
        "seed",
        "trial",
        "success",
        "completion_time_s",
        "timeout_s",
        "effective_attempt_time_s",
        "success_probability",
        "round2_entry_probability",
        "round1_time_s",
        "round2_time_s",
        "expected_rate_hz",
        "fidelity",
        "expected_fidelity",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        import csv

        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


# Import the existing private rule actions in one place. They are deliberately
# reused so validation exercises the same SeQUeNCe protocol glue as the adapter.
from sequence_qsavory_comparison.sequence.generation import _eg_action_await, _eg_action_request  # noqa: E402
