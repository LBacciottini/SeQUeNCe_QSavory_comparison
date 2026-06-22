"""Top-level SeQUeNCe simulation runner.

This module assembles the full chapter-4 comparison scenario: two elementary
links, a short-range flow on ``r1-r2``, a long-range flow on ``r1-r3`` through
swapping at ``r2``, and BBPSSW purification only on end-to-end ``r1-r3`` pairs.
"""

from __future__ import annotations

import pathlib
from typing import Any

from sequence_qsavory_comparison.common.config import resolve_config
from sequence_qsavory_comparison.common.outputs import ensure_output_dir, utc_now_iso, write_manifest, write_pairs_csv, write_summary_csv

from .generation import eg_action_await, eg_action_request, install_eg_rule
from .imports import import_sequence
from .mapping import inspect_sequence_configuration
from .network import build_network
from .purification import install_end_to_end_ep_rules
from .results import collect_pairs, summary_row
from .swapping import es_action_a, es_action_b, es_condition_a, es_condition_b


def run_sequence(config: dict[str, Any], seed: int, output_dir: str | pathlib.Path) -> dict[str, Any]:
    """Run SeQUeNCe from the shared config and write canonical outputs.

    The function is the Python-side production entry point used by CLI batch
    and sweep runners.  It resolves the shared config, builds SeQUeNCe nodes
    and channels, installs resource-manager rules for generation, swapping, and
    end-to-end purification, runs the timeline, and writes ``pairs.csv``,
    ``summary.csv``, and ``manifest.json`` into ``output_dir``.

    Args:
        config: Shared simulator-agnostic configuration dictionary.
        seed: Deterministic seed for the SeQUeNCe timeline and node random
            streams.
        output_dir: Directory for canonical run artifacts.

    Returns:
        A dictionary with ``manifest``, ``pairs``, and ``summary`` entries.  The
        same information is also written to disk using filenames from the
        resolved config.

    Example:
        >>> result = run_sequence(cfg, seed=7, output_dir="results/sequence/seed_7")  # doctest: +SKIP
        >>> result.get("summary", {}).get("simulator")  # doctest: +SKIP
        'sequence'
    """

    resolved = resolve_config(config)
    imports = import_sequence(resolved["paths"].get("sequence_path"))
    timeline, r1, r2, r3 = build_network(resolved, imports, seed)
    flow1 = resolved["resource_reservation"]["flow1"]
    flow2 = resolved["resource_reservation"]["flow2"]

    timeline.init()
    install_eg_rule(imports.Rule, r1, eg_action_request, "m12", "r2", flow1["r1_slots"], "r1", flow1["r2_slots"])
    install_eg_rule(imports.Rule, r2, eg_action_await, "m12", "r1", flow1["r2_slots"])
    install_eg_rule(imports.Rule, r1, eg_action_request, "m12", "r2", flow2["r1_slots"], "r1", flow2["r2_left_slots"])
    install_eg_rule(imports.Rule, r2, eg_action_await, "m12", "r1", flow2["r2_left_slots"])
    install_eg_rule(imports.Rule, r2, eg_action_request, "m23", "r3", flow2["r2_right_slots"], "r2", flow2["r3_slots"])
    install_eg_rule(imports.Rule, r3, eg_action_await, "m23", "r2", flow2["r3_slots"])

    target_fidelity = resolved["derived"]["target_purification_fidelity"]
    install_end_to_end_ep_rules(imports.Rule, r1, r3, flow2, target_fidelity)

    r1.resource_manager.load(imports.Rule(
        10,
        es_action_b,
        es_condition_b,
        {},
        {"index_lower": flow2["r1_slots"][0], "index_upper": flow2["r1_slots"][1], "target_node": "r3", "target_fidelity": target_fidelity},
    ))
    r3.resource_manager.load(imports.Rule(
        10,
        es_action_b,
        es_condition_b,
        {},
        {"index_lower": flow2["r3_slots"][0], "index_upper": flow2["r3_slots"][1], "target_node": "r1", "target_fidelity": target_fidelity},
    ))
    r2.resource_manager.load(imports.Rule(
        10,
        es_action_a,
        es_condition_a,
        {"succ_prob": resolved["swapping"]["success_probability"]},
        {"index_lower": flow2["r2_left_slots"][0], "index_upper": flow2["r2_right_slots"][1], "target_fidelity": target_fidelity, "left": "r1", "right": "r3"},
    ))
    timeline.run()

    pairs = collect_pairs("sequence", seed, r1)
    summary = summary_row(
        "sequence",
        seed,
        "completed",
        float(timeline.now()) * 1e-12,
        pairs,
        int(flow2["target_pairs"]),
        bool(resolved["purification"]["enabled"]),
    )
    out = ensure_output_dir(output_dir)
    write_pairs_csv(out / resolved["outputs"]["pairs_filename"], pairs)
    write_summary_csv(out / resolved["outputs"]["summary_filename"], [summary])
    manifest = {
        "schema_version": 1,
        "simulator": "sequence",
        "seed": seed,
        "created_at": utc_now_iso(),
        "raw_config": config,
        "resolved_config": resolved,
        "applied_config": inspect_sequence_configuration(config),
        "outputs": resolved["outputs"],
    }
    write_manifest(out / resolved["outputs"]["manifest_filename"], manifest)
    return {"manifest": manifest, "pairs": pairs, "summary": summary}
