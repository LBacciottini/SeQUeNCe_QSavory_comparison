"""Batch summary aggregation and plotting helpers."""

from __future__ import annotations

import csv
import pathlib
import statistics
from typing import Iterable


SUMMARY_GLOB = "*/*/summary.csv"
DEFAULT_SIMULATOR_ORDER = ("sequence", "qsavory_werner", "qsavory_exact")


def read_summary_rows(root: str | pathlib.Path) -> list[dict[str, str]]:
    """Read all simulator summary rows under a batch output directory."""

    rows: list[dict[str, str]] = []
    for path in pathlib.Path(root).glob(SUMMARY_GLOB):
        with path.open(newline="", encoding="utf-8") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


def series_by_simulator(rows: Iterable[dict[str, str]], field: str) -> dict[str, list[tuple[int, float]]]:
    """Return sorted `(seed, value)` series for a numeric summary field."""

    grouped: dict[str, list[tuple[int, float]]] = {}
    for row in rows:
        raw = row.get(field) or ""
        if not raw:
            continue
        grouped.setdefault(row["simulator"], []).append((int(row["seed"]), float(raw)))
    return {simulator: sorted(values) for simulator, values in grouped.items()}


def write_comparison_csv(rows: Iterable[dict[str, str]], path: str | pathlib.Path) -> None:
    """Write aggregate completion-time statistics by simulator."""

    rows = list(rows)
    by_simulator = {
        simulator: [value for _seed, value in values]
        for simulator, values in series_by_simulator(rows, "completion_time_s").items()
    }
    target_completed = _target_completed_counts(rows)
    out = pathlib.Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "simulator",
                "runs_with_completion_time",
                "target_completed_runs",
                "mean_completion_time_s",
                "stdev_completion_time_s",
            ],
        )
        writer.writeheader()
        for simulator in _ordered_simulators(by_simulator):
            values = by_simulator[simulator]
            writer.writerow(
                {
                    "simulator": simulator,
                    "runs_with_completion_time": len(values),
                    "target_completed_runs": target_completed.get(simulator, 0),
                    "mean_completion_time_s": statistics.fmean(values) if values else "",
                    "stdev_completion_time_s": statistics.stdev(values) if len(values) > 1 else 0.0,
                }
            )


def plot_batch_curves(
    root: str | pathlib.Path,
    output_dir: str | pathlib.Path,
    *,
    fidelity_field: str = "flow2_mean_fidelity",
) -> dict[str, pathlib.Path]:
    """Create completion-time and average-fidelity curves from batch summaries."""

    rows = read_summary_rows(root)
    out = pathlib.Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    completion_path = out / "completion_time_by_seed.png"
    fidelity_path = out / "average_fidelity_by_seed.png"
    _plot_series(
        series_by_simulator(rows, "completion_time_s"),
        completion_path,
        ylabel="Completion time (s)",
        title="Completion time by seed",
    )
    _plot_series(
        series_by_simulator(rows, fidelity_field),
        fidelity_path,
        ylabel="Average fidelity",
        title=f"{fidelity_field} by seed",
    )
    return {"completion_time": completion_path, "average_fidelity": fidelity_path}


def _ordered_simulators(mapping: dict[str, object]) -> list[str]:
    preferred = [simulator for simulator in DEFAULT_SIMULATOR_ORDER if simulator in mapping]
    remaining = sorted(simulator for simulator in mapping if simulator not in DEFAULT_SIMULATOR_ORDER)
    return preferred + remaining


def _target_completed_counts(rows: Iterable[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = (row.get("target_completed") or "").lower()
        if value in ("true", "1", "yes"):
            counts[row["simulator"]] = counts.get(row["simulator"], 0) + 1
    return counts


def _plot_series(series: dict[str, list[tuple[int, float]]], path: pathlib.Path, *, ylabel: str, title: str) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on local plotting environment
        raise RuntimeError("matplotlib is required to generate plot images") from exc

    fig, ax = plt.subplots(figsize=(8, 4.8))
    for simulator in _ordered_simulators(series):
        values = series[simulator]
        if not values:
            continue
        seeds = [seed for seed, _value in values]
        ys = [value for _seed, value in values]
        ax.plot(seeds, ys, marker="o", linewidth=1.8, markersize=3.5, label=simulator)
    ax.set_xlabel("Seed")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)
