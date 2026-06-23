"""Shared diagnostic scenarios and event aggregation.

The diagnostic layer is deliberately simulator agnostic: each simulator emits a
common event stream, and these helpers turn that stream into small stage
summaries that can be compared across SeQUeNCe and QuantumSavory.
"""

from __future__ import annotations

import copy
import csv
import json
import math
import pathlib
import statistics
from dataclasses import dataclass
from typing import Any, Iterable


DIAGNOSTIC_SCHEMA_VERSION = 1

SCENARIOS = (
    "single_lane_elementary",
    "same_link_multilane",
    "competing_flows_same_bsm",
    "two_link_no_swap",
    "eg_swap_no_purification",
    "full_reduced",
)

SCENARIO_ORDER = {scenario: index for index, scenario in enumerate(SCENARIOS)}

COMPARISON_FIELDS = (
    "scenario",
    "stage",
    "event",
    "reference_simulator",
    "candidate_simulator",
    "reference_n",
    "candidate_n",
    "reference_mean_s",
    "candidate_mean_s",
    "reference_ci95_s",
    "candidate_ci95_s",
    "reference_event_count_mean",
    "candidate_event_count_mean",
    "event_counts_match",
    "relative_gap",
    "ci95_overlaps",
)


@dataclass
class DiagnosticRecorder:
    """Collect diagnostic events for one simulator run."""

    simulator: str
    seed: int
    scenario: str
    link_length_km: float

    def __post_init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def log(
        self,
        *,
        stage: str,
        event: str,
        time_s: float,
        flow: str = "",
        link: str = "",
        node: str = "",
        slot: int | str = "",
        pair_id: int | str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Append one normalized diagnostic event."""

        self.events.append(
            {
                "simulator": self.simulator,
                "seed": self.seed,
                "link_length_km": self.link_length_km,
                "scenario": self.scenario,
                "flow": flow,
                "link": link,
                "node": node,
                "slot": slot,
                "stage": stage,
                "event": event,
                "time_s": time_s,
                "pair_id": pair_id,
                "details_json": json.dumps(details or {}, sort_keys=True),
            }
        )


def scenario_config(config: dict[str, Any], scenario: str) -> dict[str, Any]:
    """Return a shared-config copy specialized for a diagnostic scenario.

    The scenario overlays keep production defaults unless the scenario must
    disable a layer to isolate timing.  Slot ranges are kept in the same
    reservation blocks so simulator-specific mappers exercise the same paths.
    """

    if scenario not in SCENARIOS:
        raise ValueError(f"unknown diagnostic scenario {scenario!r}")
    cfg = copy.deepcopy(config)
    flow1 = cfg["resource_reservation"]["flow1"]
    flow2 = cfg["resource_reservation"]["flow2"]

    if scenario == "single_lane_elementary":
        flow1["target_pairs"] = 1
        flow1["r1_slots"] = [0, 0]
        flow1["r2_slots"] = [0, 0]
        flow2["target_pairs"] = 0
        cfg["purification"]["enabled"] = False
    elif scenario == "same_link_multilane":
        flow1["target_pairs"] = min(10, flow1["r1_slots"][1] - flow1["r1_slots"][0] + 1)
        flow2["target_pairs"] = 0
        cfg["purification"]["enabled"] = False
    elif scenario == "competing_flows_same_bsm":
        flow2["target_pairs"] = 0
        cfg["purification"]["enabled"] = False
    elif scenario == "two_link_no_swap":
        flow1["target_pairs"] = 0
        flow2["target_pairs"] = 0
        cfg["purification"]["enabled"] = False
    elif scenario == "eg_swap_no_purification":
        flow1["target_pairs"] = 0
        flow2["target_pairs"] = min(10, flow2["r1_slots"][1] - flow2["r1_slots"][0] + 1)
        cfg["purification"]["enabled"] = False
    elif scenario == "full_reduced":
        flow2["target_pairs"] = min(2, flow2["r1_slots"][1] - flow2["r1_slots"][0] + 1)
    return cfg


def summarize_events(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate event timings by simulator, seed, scenario, stage, and event."""

    groups: dict[tuple[Any, ...], list[float]] = {}
    for row in events:
        raw_time = row.get("time_s", "")
        if raw_time == "":
            continue
        key = (
            row.get("simulator", ""),
            row.get("seed", ""),
            row.get("scenario", ""),
            row.get("link_length_km", ""),
            row.get("stage", ""),
            row.get("event", ""),
        )
        groups.setdefault(key, []).append(float(raw_time))

    summaries: list[dict[str, Any]] = []
    for key, times in sorted(groups.items(), key=lambda item: tuple(str(part) for part in item[0])):
        times.sort()
        intervals = [b - a for a, b in zip(times, times[1:])]
        simulator, seed, scenario, link_length, stage, event = key
        summaries.append(
            {
                "simulator": simulator,
                "seed": seed,
                "scenario": scenario,
                "link_length_km": link_length,
                "stage": stage,
                "event": event,
                "count": len(times),
                "first_time_s": times[0] if times else "",
                "nth_time_s": times[-1] if times else "",
                "mean_interarrival_s": sum(intervals) / len(intervals) if intervals else "",
                "mean_duration_s": "",
            }
        )
    return summaries


def read_diagnostic_events(root: str | pathlib.Path) -> list[dict[str, str]]:
    """Read every diagnostic `events.csv` under a campaign root."""

    rows: list[dict[str, str]] = []
    for path in pathlib.Path(root).glob("*/*/seed_*/events.csv"):
        with path.open(newline="", encoding="utf-8") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


def read_diagnostic_stage_summaries(root: str | pathlib.Path) -> list[dict[str, str]]:
    """Read every diagnostic `stage_summary.csv` under a campaign root."""

    rows: list[dict[str, str]] = []
    for path in pathlib.Path(root).glob("*/*/seed_*/stage_summary.csv"):
        with path.open(newline="", encoding="utf-8") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


def diagnostic_metric_rows(events: Iterable[dict[str, Any]], *, terminal_events: tuple[str, ...] = ("delivered", "completed", "success")) -> list[dict[str, Any]]:
    """Collapse per-run diagnostic events to one terminal time per stage/event.

    The comparison uses the last timestamp for each `(simulator, seed, scenario,
    stage, event)` group.  For fill-time and completion diagnostics this is the
    relevant metric: time to reach the observed terminal count for that run.
    """

    grouped: dict[tuple[str, int, str, str, str], list[float]] = {}
    for event in events:
        if str(event.get("event", "")) not in terminal_events:
            continue
        raw_time = event.get("time_s", "")
        if raw_time == "":
            continue
        key = (
            str(event.get("simulator", "")),
            int(float(event.get("seed", 0))),
            str(event.get("scenario", "")),
            str(event.get("stage", "")),
            str(event.get("event", "")),
        )
        grouped.setdefault(key, []).append(float(raw_time))

    rows: list[dict[str, Any]] = []
    for (simulator, seed, scenario, stage, event), times in sorted(grouped.items()):
        rows.append(
            {
                "simulator": simulator,
                "seed": seed,
                "scenario": scenario,
                "stage": stage,
                "event": event,
                "terminal_time_s": max(times),
                "event_count": len(times),
            }
        )
    return rows


def diagnostic_metric_rows_from_stage_summaries(
    rows: Iterable[dict[str, Any]],
    *,
    terminal_events: tuple[str, ...] = ("delivered", "completed", "success"),
) -> list[dict[str, Any]]:
    """Convert compact per-run stage summaries into analyzer metric rows.

    Each simulator run writes one `stage_summary.csv` row per
    `(stage, event)` group.  The `nth_time_s` value is the same terminal time
    computed from raw events, but avoids re-reading potentially huge event
    streams during root-cause analysis.
    """

    metrics: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("event", "")) not in terminal_events:
            continue
        terminal_time = row.get("nth_time_s", "")
        if terminal_time == "":
            continue
        metrics.append(
            {
                "simulator": str(row.get("simulator", "")),
                "seed": int(float(row.get("seed", 0))),
                "scenario": str(row.get("scenario", "")),
                "stage": str(row.get("stage", "")),
                "event": str(row.get("event", "")),
                "terminal_time_s": float(terminal_time),
                "event_count": int(float(row.get("count", 0))),
            }
        )
    return metrics


def compare_diagnostic_metrics(
    metric_rows: Iterable[dict[str, Any]],
    *,
    reference_simulator: str = "sequence",
    candidate_simulator: str = "qsavory_exact",
) -> list[dict[str, Any]]:
    """Compare terminal diagnostic times between two simulators."""

    groups: dict[tuple[str, str, str, str], list[tuple[float, int]]] = {}
    for row in metric_rows:
        key = (str(row["scenario"]), str(row["stage"]), str(row["event"]), str(row["simulator"]))
        groups.setdefault(key, []).append((float(row["terminal_time_s"]), int(float(row.get("event_count", 0)))))

    comparisons: list[dict[str, Any]] = []
    scenario_stage_events = sorted({(scenario, stage, event) for scenario, stage, event, _sim in groups}, key=lambda item: (SCENARIO_ORDER.get(item[0], 999), item[1], item[2]))
    for scenario, stage, event in scenario_stage_events:
        ref_group = groups.get((scenario, stage, event, reference_simulator), [])
        cand_group = groups.get((scenario, stage, event, candidate_simulator), [])
        if not ref_group or not cand_group:
            continue
        ref = [item[0] for item in ref_group]
        cand = [item[0] for item in cand_group]
        ref_counts = [item[1] for item in ref_group]
        cand_counts = [item[1] for item in cand_group]
        ref_mean, ref_ci = _mean_ci95(ref)
        cand_mean, cand_ci = _mean_ci95(cand)
        ref_count_mean = statistics.fmean(ref_counts)
        cand_count_mean = statistics.fmean(cand_counts)
        gap = (ref_mean - cand_mean) / cand_mean if cand_mean else math.inf
        overlaps = (ref_mean - ref_ci) <= (cand_mean + cand_ci) and (cand_mean - cand_ci) <= (ref_mean + ref_ci)
        comparisons.append(
            {
                "scenario": scenario,
                "stage": stage,
                "event": event,
                "reference_simulator": reference_simulator,
                "candidate_simulator": candidate_simulator,
                "reference_n": len(ref),
                "candidate_n": len(cand),
                "reference_mean_s": ref_mean,
                "candidate_mean_s": cand_mean,
                "reference_ci95_s": ref_ci,
                "candidate_ci95_s": cand_ci,
                "reference_event_count_mean": ref_count_mean,
                "candidate_event_count_mean": cand_count_mean,
                "event_counts_match": math.isclose(ref_count_mean, cand_count_mean, rel_tol=0.0, abs_tol=0.0),
                "relative_gap": gap,
                "ci95_overlaps": overlaps,
            }
        )
    return comparisons


def first_divergence(comparisons: Iterable[dict[str, Any]], *, minimum_relative_gap: float = 0.05) -> dict[str, Any] | None:
    """Return the first non-overlapping diagnostic comparison."""

    ordered = sorted(
        comparisons,
        key=lambda row: (SCENARIO_ORDER.get(str(row["scenario"]), 999), str(row["stage"]), str(row["event"])),
    )
    for row in ordered:
        if not bool(row.get("event_counts_match", True)):
            return row
        if not bool(row["ci95_overlaps"]) and abs(float(row["relative_gap"])) >= minimum_relative_gap:
            return row
    return None


def write_diagnostic_comparison_csv(path: str | pathlib.Path, rows: Iterable[dict[str, Any]]) -> None:
    """Write analyzer comparison rows."""

    with pathlib.Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMPARISON_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in COMPARISON_FIELDS})


def write_root_cause_report(path: str | pathlib.Path, comparisons: list[dict[str, Any]], divergence: dict[str, Any] | None) -> None:
    """Write a compact markdown root-cause report."""

    lines = ["# Diagnostic Root-Cause Report", ""]
    if divergence is None:
        lines.extend(
            [
                "No statistically significant divergence was found with the configured criterion.",
                "",
                "Inspect `diagnostic_comparison.csv` for low-power comparisons or missing stages.",
            ]
        )
    else:
        lines.extend(
            [
                "## First Divergence",
                "",
                f"- Scenario: `{divergence['scenario']}`",
                f"- Stage: `{divergence['stage']}`",
                f"- Event: `{divergence['event']}`",
                f"- Reference: `{divergence['reference_simulator']}` mean `{float(divergence['reference_mean_s']):.6g}s` +/- `{float(divergence['reference_ci95_s']):.3g}s`",
                f"- Candidate: `{divergence['candidate_simulator']}` mean `{float(divergence['candidate_mean_s']):.6g}s` +/- `{float(divergence['candidate_ci95_s']):.3g}s`",
                f"- Event counts: `{float(divergence['reference_event_count_mean']):.3g}` vs `{float(divergence['candidate_event_count_mean']):.3g}`",
                f"- Relative gap: `{float(divergence['relative_gap']):.3%}`",
                "",
                "## Interpretation",
                "",
                _interpret_divergence(str(divergence["scenario"])),
            ]
        )
    lines.extend(["", "## Compared Stages", ""])
    for row in comparisons:
        lines.append(
            f"- `{row['scenario']}` / `{row['stage']}` / `{row['event']}`: "
            f"{row['reference_simulator']}={float(row['reference_mean_s']):.6g}s, "
            f"{row['candidate_simulator']}={float(row['candidate_mean_s']):.6g}s, "
            f"counts={float(row['reference_event_count_mean']):.3g}/{float(row['candidate_event_count_mean']):.3g}, "
            f"gap={float(row['relative_gap']):.2%}, overlap={row['ci95_overlaps']}"
        )
    pathlib.Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _mean_ci95(values: list[float]) -> tuple[float, float]:
    mean = statistics.fmean(values)
    ci95 = 1.96 * statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else 0.0
    return mean, ci95


def _interpret_divergence(scenario: str) -> str:
    if scenario in {"single_lane_elementary", "same_link_multilane"}:
        return "The mismatch appears in elementary generation. Fix the attempt-time or elementary multiplexing model before inspecting swap or purification."
    if scenario == "competing_flows_same_bsm":
        return "The mismatch appears when logical flows share the same BSM/link resources. Add or correct shared-resource contention in the QuantumSavory comparison adapter, or remove unintended contention from SeQUeNCe if the trace shows it is adapter-induced."
    if scenario == "two_link_no_swap":
        return "The mismatch appears when both elementary links are active. Inspect middle-node rule priorities and per-link resource symmetry."
    if scenario == "eg_swap_no_purification":
        return "The mismatch appears at swap consumption or memory release. Compare swap-ready and swapped-delivered events before changing BBPSSW."
    if scenario == "full_reduced":
        return "The mismatch appears only after purification or completion accounting. Inspect BBPSSW candidate selection, handshake timing, and completion definition."
    return "The scenario is not recognized by the canned interpretation; inspect the event traces directly."
