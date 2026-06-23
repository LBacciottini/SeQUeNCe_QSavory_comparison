"""Batch summary aggregation and plotting helpers.

The plotting API consumes the canonical `summary.csv` files written by both
simulators. It has two modes: seeded batch plots with seed on the x-axis and
link-length sweep plots with elementary link length on the x-axis.
"""

from __future__ import annotations

import csv
import json
import pathlib
import statistics
from typing import Iterable


SUMMARY_GLOB = "*/*/summary.csv"
SWEEP_SUMMARY_GLOB = "*/*/*/summary.csv"
DEFAULT_SIMULATOR_ORDER = ("sequence", "qsavory_werner", "qsavory_exact")
COLORBLIND_PALETTE = (
    "#0072B2",  # blue
    "#D55E00",  # vermillion
    "#009E73",  # bluish green
    "#CC79A7",  # reddish purple
    "#E69F00",  # orange
    "#56B4E9",  # sky blue
    "#F0E442",  # yellow
)
PLOT_STYLE = {
    "font.size": 14,
    "axes.titlesize": 16,
    "axes.labelsize": 15,
    "xtick.labelsize": 16,
    "ytick.labelsize": 16,
    "legend.fontsize": 12,
    "legend.title_fontsize": 12,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
}


def read_summary_rows(root: str | pathlib.Path) -> list[dict[str, str]]:
    """Read all simulator summary rows under a batch output directory.

    Args:
        root: Batch root containing `<simulator>/seed_<n>/summary.csv`
            directories.

    Returns:
        Raw CSV rows as dictionaries. Values are strings because they come
        directly from `csv.DictReader`.
    """

    rows: list[dict[str, str]] = []
    for path in pathlib.Path(root).glob(SUMMARY_GLOB):
        with path.open(newline="", encoding="utf-8") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


def read_sweep_summary_rows(root: str | pathlib.Path) -> list[dict[str, str]]:
    """Read sweep summaries and attach link length from each run manifest.

    Args:
        root: Sweep root containing `link_XXXkm/<simulator>/seed_<n>/`
            directories.

    Returns:
        Summary rows with an added `link_length_km` string field.
    """

    rows: list[dict[str, str]] = []
    for path in pathlib.Path(root).glob(SWEEP_SUMMARY_GLOB):
        manifest_path = path.with_name("manifest.json")
        if not manifest_path.exists():
            continue
        with manifest_path.open(encoding="utf-8") as handle:
            manifest = json.load(handle)
        link_length = manifest["resolved_config"]["topology"]["link_length_km"]
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                enriched = dict(row)
                enriched["link_length_km"] = str(link_length)
                rows.append(enriched)
    return rows


def series_by_simulator(rows: Iterable[dict[str, str]], field: str) -> dict[str, list[tuple[int, float]]]:
    """Return sorted `(seed, value)` series for a numeric summary field.

    Args:
        rows: Summary rows from `read_summary_rows`.
        field: Numeric CSV column to plot or aggregate.

    Returns:
        Mapping from simulator label to seed-sorted numeric values. Rows with
        empty values for `field` are skipped.
    """

    grouped: dict[str, list[tuple[int, float]]] = {}
    for row in rows:
        raw = row.get(field) or ""
        if not raw:
            continue
        grouped.setdefault(row["simulator"], []).append((int(row["seed"]), float(raw)))
    return {simulator: sorted(values) for simulator, values in grouped.items()}


def write_comparison_csv(rows: Iterable[dict[str, str]], path: str | pathlib.Path) -> None:
    """Write aggregate completion-time statistics by simulator.

    Args:
        rows: Batch summary rows.
        path: Destination aggregate CSV path.

    Example:
        ```python
        rows = read_summary_rows("outputs/batch")
        write_comparison_csv(rows, "outputs/batch/comparison.csv")
        ```
    """

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


def write_sweep_comparison_csv(
    rows: Iterable[dict[str, str]],
    path: str | pathlib.Path,
    *,
    fidelity_field: str = "flow2_mean_fidelity",
) -> None:
    """Write aggregate sweep statistics by link length and simulator.

    Args:
        rows: Sweep summary rows with `link_length_km` populated.
        path: Destination aggregate CSV path.
        fidelity_field: Summary fidelity column to aggregate. Defaults to the
            end-to-end flow2 fidelity.
    """

    rows = list(rows)
    grouped: dict[tuple[float, str], list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault((float(row["link_length_km"]), row["simulator"]), []).append(row)
    out = pathlib.Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "link_length_km",
            "simulator",
            "runs",
            "target_completed_runs",
            "runs_with_completion_time",
            "mean_completion_time_s",
            "stdev_completion_time_s",
            "ci95_completion_time_s",
            f"runs_with_{fidelity_field}",
            f"mean_{fidelity_field}",
            f"stdev_{fidelity_field}",
            f"ci95_{fidelity_field}",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for link_length, simulator in _ordered_sweep_keys(grouped):
            group = grouped[(link_length, simulator)]
            completion_values = _numeric_values(group, "completion_time_s")
            fidelity_values = _numeric_values(group, fidelity_field)
            writer.writerow(
                {
                    "link_length_km": _format_number(link_length),
                    "simulator": simulator,
                    "runs": len(group),
                    "target_completed_runs": sum(_is_truthy(row.get("target_completed", "")) for row in group),
                    "runs_with_completion_time": len(completion_values),
                    "mean_completion_time_s": _mean_or_blank(completion_values),
                    "stdev_completion_time_s": _stdev_or_zero(completion_values),
                    "ci95_completion_time_s": _ci95_or_zero(completion_values),
                    f"runs_with_{fidelity_field}": len(fidelity_values),
                    f"mean_{fidelity_field}": _mean_or_blank(fidelity_values),
                    f"stdev_{fidelity_field}": _stdev_or_zero(fidelity_values),
                    f"ci95_{fidelity_field}": _ci95_or_zero(fidelity_values),
                }
            )


def plot_batch_curves(
    root: str | pathlib.Path,
    output_dir: str | pathlib.Path,
    *,
    fidelity_field: str = "flow2_mean_fidelity",
) -> dict[str, pathlib.Path]:
    """Create completion-time and average-fidelity curves from batch summaries.

    Args:
        root: Batch root to scan for `summary.csv` files.
        output_dir: Directory where PDF files should be written.
        fidelity_field: Summary column used for the fidelity plot.

    Returns:
        Paths keyed by `"completion_time"` and `"average_fidelity"`.

    Raises:
        RuntimeError: If `matplotlib` is not installed.
    """

    rows = read_summary_rows(root)
    out = pathlib.Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    completion_path = out / "completion_time_by_seed.pdf"
    fidelity_path = out / "average_fidelity_by_seed.pdf"
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
        title="Distilled pairs e2e fidelity",
    )
    return {"completion_time": completion_path, "average_fidelity": fidelity_path}


def plot_sweep_curves(
    root: str | pathlib.Path,
    output_dir: str | pathlib.Path,
    *,
    fidelity_field: str = "flow2_mean_fidelity",
) -> dict[str, pathlib.Path]:
    """Create completion-time and average-fidelity curves by link length.

    Args:
        root: Sweep root to scan for nested summaries and manifests.
        output_dir: Directory where PDF files should be written.
        fidelity_field: Summary column used for the fidelity plot.

    Returns:
        Paths keyed by `"completion_time"` and `"average_fidelity"`.

    Raises:
        RuntimeError: If `matplotlib` is not installed.
    """

    rows = read_sweep_summary_rows(root)
    out = pathlib.Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    completion_path = out / "completion_time_by_link_length.pdf"
    fidelity_path = out / "average_fidelity_by_link_length.pdf"
    _plot_errorbar_series(
        sweep_series_by_simulator(rows, "completion_time_s"),
        completion_path,
        ylabel="Completion time (s)",
        title="Completion time by link length",
    )
    _plot_errorbar_series(
        sweep_series_by_simulator(rows, fidelity_field),
        fidelity_path,
        ylabel="Average fidelity",
        title="Distilled pairs e2e fidelity",
    )
    return {"completion_time": completion_path, "average_fidelity": fidelity_path}


def sweep_series_by_simulator(rows: Iterable[dict[str, str]], field: str) -> dict[str, list[tuple[float, float, float]]]:
    """Return sorted `(link_length_km, mean, ci95)` series for a numeric field.

    Args:
        rows: Sweep summary rows.
        field: Numeric field to aggregate by link length and simulator.

    Returns:
        Mapping from simulator label to tuples of link length, sample mean, and
        95% confidence interval half-width.
    """

    grouped: dict[tuple[str, float], list[float]] = {}
    for row in rows:
        raw = row.get(field) or ""
        if not raw:
            continue
        grouped.setdefault((row["simulator"], float(row["link_length_km"])), []).append(float(raw))
    by_simulator: dict[str, list[tuple[float, float, float]]] = {}
    for (simulator, link_length), values in grouped.items():
        by_simulator.setdefault(simulator, []).append(
            (link_length, statistics.fmean(values), _ci95_or_zero(values))
        )
    return {simulator: sorted(values) for simulator, values in by_simulator.items()}


def _ordered_simulators(mapping: dict[str, object]) -> list[str]:
    preferred = [simulator for simulator in DEFAULT_SIMULATOR_ORDER if simulator in mapping]
    remaining = sorted(simulator for simulator in mapping if simulator not in DEFAULT_SIMULATOR_ORDER)
    return preferred + remaining


def _target_completed_counts(rows: Iterable[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        if _is_truthy(row.get("target_completed", "")):
            counts[row["simulator"]] = counts.get(row["simulator"], 0) + 1
    return counts


def _ordered_sweep_keys(mapping: dict[tuple[float, str], object]) -> list[tuple[float, str]]:
    ordered: list[tuple[float, str]] = []
    for link_length in sorted({key[0] for key in mapping}):
        simulators = {simulator for length, simulator in mapping if length == link_length}
        ordered.extend((link_length, simulator) for simulator in _ordered_simulators({sim: None for sim in simulators}))
    return ordered


def _numeric_values(rows: Iterable[dict[str, str]], field: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        raw = row.get(field) or ""
        if raw:
            values.append(float(raw))
    return values


def _mean_or_blank(values: list[float]) -> float | str:
    return statistics.fmean(values) if values else ""


def _stdev_or_zero(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else 0.0


def _ci95_or_zero(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return 1.96 * statistics.stdev(values) / (len(values) ** 0.5)


def _is_truthy(value: str) -> bool:
    return (value or "").lower() in ("true", "1", "yes")


def _format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.12g}"


def _plot_series(series: dict[str, list[tuple[int, float]]], path: pathlib.Path, *, ylabel: str, title: str) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on local plotting environment
        raise RuntimeError("matplotlib is required to generate plot images") from exc

    plt.rcParams.update(PLOT_STYLE)
    fig, ax = plt.subplots(figsize=(9, 5.4))
    for index, simulator in enumerate(_ordered_simulators(series)):
        values = series[simulator]
        if not values:
            continue
        seeds = [seed for seed, _value in values]
        ys = [value for _seed, value in values]
        ax.plot(
            seeds,
            ys,
            marker="o",
            linewidth=2.2,
            markersize=5.0,
            color=COLORBLIND_PALETTE[index % len(COLORBLIND_PALETTE)],
            label=simulator,
        )
    ax.set_xlabel("Seed")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    ax.legend(frameon=False)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_errorbar_series(
    series: dict[str, list[tuple[float, float, float]]],
    path: pathlib.Path,
    *,
    ylabel: str,
    title: str,
) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on local plotting environment
        raise RuntimeError("matplotlib is required to generate plot images") from exc

    plt.rcParams.update(PLOT_STYLE)
    fig, ax = plt.subplots(figsize=(9, 5.4))
    for index, simulator in enumerate(_ordered_simulators(series)):
        values = series[simulator]
        if not values:
            continue
        xs = [link_length for link_length, _mean, _ci in values]
        means = [mean for _link_length, mean, _ci in values]
        cis = [ci for _link_length, _mean, ci in values]
        ax.errorbar(
            xs,
            means,
            yerr=cis,
            marker="o",
            linewidth=2.2,
            markersize=5.0,
            capsize=4,
            color=COLORBLIND_PALETTE[index % len(COLORBLIND_PALETTE)],
            label=simulator,
        )
    ax.set_xlabel("Elementary link length (km)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    ax.legend(frameon=False)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180)
    plt.close(fig)
