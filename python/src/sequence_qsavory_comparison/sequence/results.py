"""Canonical SeQUeNCe result collection and summary helpers."""

from __future__ import annotations

import statistics
from typing import Any


def collect_pairs(simulator: str, seed: int, router: Any) -> list[dict[str, Any]]:
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
    flow1 = [p for p in pairs if p["flow"] == "flow1"]
    observed_flow2 = [p for p in pairs if p["flow"] == "flow2"]
    purified_flow2 = [p for p in observed_flow2 if p.get("status") == "PURIFIED"]
    completion = ""
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
