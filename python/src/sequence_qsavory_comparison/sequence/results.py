"""Canonical SeQUeNCe result collection and summary helpers.

These helpers translate SeQUeNCe memory-manager state into the simulator-neutral
CSV schema consumed by batch aggregation and plotting.  Only the local ``r1``
view is collected because the comparison completion criterion is expressed in
terms of usable pairs held at ``r1``.
"""

from __future__ import annotations

import statistics
from typing import Any


def collect_pairs(simulator: str, seed: int, router: Any) -> list[dict[str, Any]]:
    """Collect delivered pairs from one SeQUeNCe router.

    Args:
        simulator: Simulator label written to each row, normally
            ``"sequence"``.
        seed: Simulation seed written to each row.
        router: Router whose resource manager owns the memory records to
            inspect.

    Returns:
        Row dictionaries matching the canonical ``pairs.csv`` schema.  Flow is
        inferred from the remote node: ``r2`` means flow 1, ``r3`` means flow 2.
    """

    rows = []
    for info in router.resource_manager.memory_manager:
        if info.state not in ("ENTANGLED", "PURIFIED") or info.entangle_time <= 0:
            continue
        flow = "flow2" if info.remote_node == "r3" else "flow1" if info.remote_node == "r2" else "other"
        rows.append(
            {
                "simulator": simulator,
                "seed": seed,
                "flow": flow,
                "local_node": router.name,
                "local_slot": info.index,
                "remote_node": info.remote_node,
                "remote_slot": info.remote_memo,
                "pair_id": "",
                "delivery_time_s": info.entangle_time * 1e-12,
                "fidelity": info.fidelity,
                "status": info.state,
            }
        )
    return rows


def summary_row(
    simulator: str,
    seed: int,
    status: str,
    runtime_s: float,
    pairs: list[dict[str, Any]],
    target_pairs: int,
    require_purified_flow2: bool = False,
) -> dict[str, Any]:
    """Summarize one SeQUeNCe run using the canonical summary schema.

    Args:
        simulator: Simulator label.
        seed: Simulation seed.
        status: Run status string, for example ``"completed"``.
        runtime_s: Simulated runtime in seconds.
        pairs: Rows returned by :func:`collect_pairs`.
        target_pairs: Number of flow-2 end-to-end pairs requested by the
            scenario.
        require_purified_flow2: When true, completion requires all target
            flow-2 pairs to exist and at least ``target_pairs - 1`` of them to
            carry ``PURIFIED`` status.

    Returns:
        A dictionary matching the canonical ``summary.csv`` schema, including
        delivered counts, completion time, and mean fidelities by flow.
    """

    flow1 = [p for p in pairs if p["flow"] == "flow1"]
    observed_flow2 = [p for p in pairs if p["flow"] == "flow2"]
    purified_flow2 = [p for p in observed_flow2 if p.get("status") == "PURIFIED"]
    completion = ""
    if target_pairs <= 0:
        target_completed = True
        return {
            "simulator": simulator,
            "seed": seed,
            "status": status,
            "runtime_s": runtime_s,
            "completion_time_s": completion,
            "target_pairs": target_pairs,
            "target_completed": target_completed,
            "flow1_delivered": len(flow1),
            "flow2_delivered": len(observed_flow2),
            "flow1_mean_fidelity": statistics.fmean(float(p["fidelity"]) for p in flow1) if flow1 else "",
            "flow2_mean_fidelity": statistics.fmean(float(p["fidelity"]) for p in observed_flow2) if observed_flow2 else "",
        }
    if require_purified_flow2:
        required_purified = max(target_pairs - 1, 0)
        target_completed = len(observed_flow2) >= target_pairs and len(purified_flow2) >= required_purified
        if target_completed:
            flow2_times = sorted(float(p["delivery_time_s"]) for p in observed_flow2)
            purified_times = sorted(float(p["delivery_time_s"]) for p in purified_flow2)
            completion = flow2_times[target_pairs - 1]
            if required_purified:
                completion = max(completion, purified_times[required_purified - 1])
    else:
        target_completed = len(observed_flow2) >= target_pairs
        if observed_flow2:
            times = sorted(float(p["delivery_time_s"]) for p in observed_flow2)
            completion = times[min(target_pairs, len(times)) - 1]
    return {
        "simulator": simulator,
        "seed": seed,
        "status": status,
        "runtime_s": runtime_s,
        "completion_time_s": completion,
        "target_pairs": target_pairs,
        "target_completed": target_completed,
        "flow1_delivered": len(flow1),
        "flow2_delivered": len(observed_flow2),
        "flow1_mean_fidelity": statistics.fmean(float(p["fidelity"]) for p in flow1) if flow1 else "",
        "flow2_mean_fidelity": statistics.fmean(float(p["fidelity"]) for p in observed_flow2) if observed_flow2 else "",
    }


_collect_pairs = collect_pairs
_summary_row = summary_row
