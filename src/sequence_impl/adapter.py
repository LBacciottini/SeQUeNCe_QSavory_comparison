"""Adapt the shared experiment config to SeQUeNCe.

The implementation keeps all SeQUeNCe imports lazy so common tests can run on
machines where the `sequence` package is not installed. The adapter also
provides an inspection function that reports every applied simulator parameter;
tests compare this report against the shared config to catch mapping drift.
"""

from __future__ import annotations

import pathlib
import statistics
import sys
from dataclasses import dataclass
from typing import Any

from src.common.config import resolve_config
from src.common.outputs import ensure_output_dir, utc_now_iso, write_manifest, write_pairs_csv, write_summary_csv


@dataclass(frozen=True)
class SequenceImports:
    """Container for SeQUeNCe symbols used by this adapter."""

    Timeline: Any
    QuantumRouter: Any
    BSMNode: Any
    ClassicalChannel: Any
    QuantumChannel: Any
    Rule: Any
    ResourceManager: Any
    MemoryInfo: Any
    EntanglementGenerationA: Any
    BBPSSWProtocol: Any
    EntanglementSwappingA: Any
    EntanglementSwappingB: Any


def _import_sequence(sequence_path: str | None = None) -> SequenceImports:
    """Import SeQUeNCe from an optional local checkout path."""

    if sequence_path:
        path = str(pathlib.Path(sequence_path).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)

    from sequence.kernel.timeline import Timeline
    from sequence.topology.node import QuantumRouter, BSMNode
    from sequence.components.optical_channel import ClassicalChannel, QuantumChannel
    from sequence.resource_management.rule_manager import Rule
    from sequence.resource_management.resource_manager import ResourceManager
    from sequence.resource_management.memory_manager import MemoryInfo
    from sequence.entanglement_management.generation import EntanglementGenerationA
    from sequence.entanglement_management.purification import BBPSSWProtocol
    from sequence.entanglement_management.swapping import EntanglementSwappingA, EntanglementSwappingB

    return SequenceImports(
        Timeline,
        QuantumRouter,
        BSMNode,
        ClassicalChannel,
        QuantumChannel,
        Rule,
        ResourceManager,
        MemoryInfo,
        EntanglementGenerationA,
        BBPSSWProtocol,
        EntanglementSwappingA,
        EntanglementSwappingB,
    )


def _inclusive_range(range_pair: list[int]) -> range:
    """Convert `[lo, hi]` inclusive config ranges into Python ranges."""

    return range(int(range_pair[0]), int(range_pair[1]) + 1)


def inspect_sequence_configuration(config: dict[str, Any]) -> dict[str, Any]:
    """Return the exact SeQUeNCe settings implied by the shared config."""

    resolved = resolve_config(config)
    derived = resolved["derived"]
    memories = resolved["memories"]
    detectors = resolved["detectors"]
    reservation = resolved["resource_reservation"]
    flow1 = reservation["flow1"]
    flow2 = reservation["flow2"]

    return {
        "memory_counts": {
            "r1": int(memories["r1_count"]),
            "r2": int(memories["r2_count"]),
            "r3": int(memories["r3_count"]),
        },
        "memory_parameters": {
            "raw_fidelity": derived["barrett_kok_raw_fidelity"],
            "coherence_time_s": -1.0,
            "decoherence_rate_hz": 0.0,
            "cutoff_enabled": False,
            "frequency_hz": derived["memory_frequency_hz"],
            "efficiency": derived["source_transmissivity"],
        },
        "detectors": {
            "efficiency": float(detectors["efficiency"]),
            "dark_count_probability": float(detectors["dark_count_probability"]),
            "dark_count_rate_hz": float(detectors["dark_count_rate_hz"]),
            "count_rate_hz": float(detectors["count_rate_hz"]),
            "time_resolution_ps": int(detectors["time_resolution_ps"]),
        },
        "channels": {
            "quantum_distance_m": derived["half_link_m"],
            "quantum_attenuation_db_per_m": derived["sequence_quantum_attenuation_db_per_m"],
            "quantum_delay_ps": derived["quantum_delay_ps"],
            "classical_delay_ps": derived["classical_delay_ps"],
            "quantum_frequency_hz": float(resolved["optics"]["quantum_channel_frequency_hz"]),
        },
        "barrett_kok_timing": {
            "full_success_probability": derived["barrett_kok_full_success_probability"],
            "round2_entry_probability": derived["barrett_kok_round2_entry_probability"],
            "round1_time_s": derived["barrett_kok_round1_time_s"],
            "round2_time_s": derived["barrett_kok_round2_time_s"],
            "two_round_time_s": derived["barrett_kok_two_round_time_s"],
            "resource_request_arrival_ps": derived["barrett_kok_resource_request_arrival_ps"],
            "protocol_start_primary_ps": derived["barrett_kok_protocol_start_primary_ps"],
            "protocol_start_nonprimary_ps": derived["barrett_kok_protocol_start_nonprimary_ps"],
            "memory_period_ps": derived["barrett_kok_memory_period_ps"],
            "round1_min_emit_ps": derived["barrett_kok_round1_min_emit_ps"],
            "round1_emit_ps": derived["barrett_kok_round1_emit_ps"],
            "round1_failure_time_ps": derived["barrett_kok_round1_failure_time_ps"],
            "round2_min_emit_ps": derived["barrett_kok_round2_min_emit_ps"],
            "round2_emit_ps": derived["barrett_kok_round2_emit_ps"],
            "two_round_time_ps": derived["barrett_kok_two_round_time_ps"],
            "round2_increment_time_ps": derived["barrett_kok_round2_increment_time_ps"],
            "effective_attempt_time_s": derived["barrett_kok_effective_attempt_time_s"],
            "expected_rate_hz": derived["barrett_kok_expected_rate_hz"],
        },
        "rules": {
            "flow1_r1_slots": flow1["r1_slots"],
            "flow1_r2_slots": flow1["r2_slots"],
            "flow2_r1_slots": flow2["r1_slots"],
            "flow2_r2_left_slots": flow2["r2_left_slots"],
            "flow2_r2_right_slots": flow2["r2_right_slots"],
            "flow2_r3_slots": flow2["r3_slots"],
            "purification_scope": "end_to_end_only",
            "purification_request_node": "r1",
            "purification_response_node": "r3",
            "purification_request_slots": flow2["r1_slots"],
            "purification_response_slots": flow2["r3_slots"],
            "purification_target_fidelity": derived["target_purification_fidelity"],
            "swap_success_probability": float(resolved["swapping"]["success_probability"]),
            "swap_fidelity_model": "ideal",
        },
    }


def _make_router_class(imports: SequenceImports, resolved: dict[str, Any]):
    """Create a RouterNode class bound to this resolved configuration."""

    raw_fidelity = resolved["derived"]["barrett_kok_raw_fidelity"]
    memory_frequency = resolved["derived"]["memory_frequency_hz"]
    source_transmissivity = float(resolved["derived"]["source_transmissivity"])

    class RouterNode(imports.QuantumRouter):
        def __init__(self, name: str, timeline: Any, memo_size: int):
            super().__init__(name, timeline, memo_size=memo_size)
            memory_array_name = f"{name}.MemoryArray"
            memory_array = self.get_components_by_type("MemoryArray")[0]
            memory_array.update_memory_params("raw_fidelity", raw_fidelity)
            memory_array.update_memory_params("fidelity", 0)
            memory_array.update_memory_params("frequency", memory_frequency)
            memory_array.update_memory_params("efficiency", source_transmissivity)
            memory_array.update_memory_params("coherence_time", -1)
            memory_array.update_memory_params("decoherence_rate", 0)
            memory_array.update_memory_params("cutoff_flag", False)
            self.resource_manager = imports.ResourceManager(self, memory_array_name)

        def receive_message(self, src: str, msg: Any) -> None:
            if msg.receiver == "resource_manager":
                self.resource_manager.received_message(src, msg)
                return
            if msg.receiver is None:
                for protocol in [p for p in self.protocols if p.protocol_type == msg.protocol_type]:
                    protocol.received_message(src, msg)
                return
            for protocol in self.protocols:
                if protocol.name == msg.receiver:
                    protocol.received_message(src, msg)
                    break

        def get_idle_memory(self, info: Any) -> None:
            return None

        def get(self, photon: Any, **kwargs: Any) -> None:
            self.send_qubit(kwargs["dst"], photon)

    return RouterNode


def _rule_condition_raw(memory_info: Any, manager: Any, args: dict[str, Any]) -> list[Any]:
    if memory_info.state == "RAW" and int(args["index_lower"]) <= memory_info.index <= int(args["index_upper"]):
        return [memory_info]
    return []


def _eg_match_func(protocols: list[Any], args: dict[str, Any]) -> Any:
    imports = _import_sequence(None)
    for protocol in protocols:
        if not isinstance(protocol, imports.EntanglementGenerationA):
            continue
        memory_array = protocol.owner.get_components_by_type("MemoryArray")[0]
        if protocol.remote_node_name == args["remote_node"]:
            idx = memory_array.memories.index(protocol.memory)
            if int(args["index_lower"]) <= idx <= int(args["index_upper"]):
                return protocol
    return None


def _eg_action_request(memories_info: list[Any], args: dict[str, Any]) -> list[Any]:
    imports = _import_sequence(None)
    memory = memories_info[0].memory
    protocol = imports.EntanglementGenerationA.create(None, "EGA." + memory.name, args["mid_name"], args["other_name"], memory)
    req_args = {
        "remote_node": args["node_name"],
        "index_upper": args["index_upper"],
        "index_lower": args["index_lower"],
    }
    return [protocol, [args["other_name"]], [_eg_match_func], [req_args]]


def _eg_action_await(memories_info: list[Any], args: dict[str, Any]) -> list[Any]:
    imports = _import_sequence(None)
    memory = memories_info[0].memory
    protocol = imports.EntanglementGenerationA.create(None, "EGA." + memory.name, args["mid_name"], args["other_name"], memory)
    return [protocol, [None], [None], [None]]


def _install_eg_rule(rule_cls: Any, node: Any, action: Any, mid: str, other: str, slot_range: list[int], node_name: str | None = None, remote_range: list[int] | None = None) -> None:
    action_args = {"mid_name": mid, "other_name": other}
    if node_name is not None and remote_range is not None:
        action_args.update({"node_name": node_name, "index_lower": remote_range[0], "index_upper": remote_range[1]})
    condition_args = {"index_lower": slot_range[0], "index_upper": slot_range[1]}
    node.resource_manager.load(rule_cls(10, action, _rule_condition_raw, action_args, condition_args))


def _ep_condition_request(memory_info: Any, manager: Any, args: dict[str, Any]) -> list[Any]:
    if not (int(args["index_lower"]) <= memory_info.index <= int(args["index_upper"])):
        return []
    remote_node = args.get("remote_node")
    if remote_node is not None and memory_info.remote_node != remote_node:
        return []
    if memory_info.state != "ENTANGLED" or memory_info.fidelity >= float(args["target_fidelity"]):
        return []
    for info in manager:
        if info is memory_info:
            continue
        if not (int(args["index_lower"]) <= info.index <= int(args["index_upper"])):
            continue
        if remote_node is not None and info.remote_node != remote_node:
            continue
        if info.state == "ENTANGLED" and info.remote_node == memory_info.remote_node and info.fidelity == memory_info.fidelity:
            return [memory_info, info]
    return []


def _ep_condition_await(memory_info: Any, manager: Any, args: dict[str, Any]) -> list[Any]:
    if int(args["index_lower"]) <= memory_info.index <= int(args["index_upper"]):
        remote_node = args.get("remote_node")
        if remote_node is not None and memory_info.remote_node != remote_node:
            return []
        if memory_info.state == "ENTANGLED" and memory_info.fidelity < float(args["target_fidelity"]):
            return [memory_info]
    return []


def _ep_match_func(protocols: list[Any], args: dict[str, Any]) -> Any:
    imports = _import_sequence(None)
    matches: list[Any] = []
    for protocol in protocols:
        if not isinstance(protocol, imports.BBPSSWProtocol):
            continue
        if protocol.kept_memo.name == args["remote1"]:
            matches.insert(0, protocol)
        if protocol.kept_memo.name == args["remote2"]:
            matches.insert(1, protocol)
    if len(matches) != 2:
        return None
    protocols.remove(matches[1])
    matches[1].rule.protocols.remove(matches[1])
    matches[1].kept_memo.detach(matches[1])
    matches[0].meas_memo = matches[1].kept_memo
    matches[0].memories = [matches[0].kept_memo, matches[0].meas_memo]
    matches[0].name = matches[0].name + "." + matches[0].meas_memo.name
    matches[0].meas_memo.attach(matches[0])
    return matches[0]


def _ep_action_request(memories_info: list[Any], args: dict[str, Any]) -> list[Any]:
    imports = _import_sequence(None)
    memories = [info.memory for info in memories_info]
    protocol = imports.BBPSSWProtocol.create(None, f"EP.{memories[0].name}.{memories[1].name}", memories[0], memories[1])
    req_args = {"remote1": memories_info[0].remote_memo, "remote2": memories_info[1].remote_memo}
    return [protocol, [memories_info[0].remote_node], [_ep_match_func], [req_args]]


def _ep_action_await(memories_info: list[Any], args: dict[str, Any]) -> list[Any]:
    imports = _import_sequence(None)
    memory = memories_info[0].memory
    protocol = imports.BBPSSWProtocol.create(None, "EP." + memory.name, memory, None)
    return [protocol, [None], [None], [None]]


def _install_ep_rule(rule_cls: Any, node: Any, action: Any, condition: Any, slot_range: list[int], target_fidelity: float, remote_node: str | None = None) -> None:
    args = {"index_lower": slot_range[0], "index_upper": slot_range[1], "target_fidelity": target_fidelity}
    if remote_node is not None:
        args["remote_node"] = remote_node
    node.resource_manager.load(rule_cls(10, action, condition, {}, args))


def _install_end_to_end_ep_rules(rule_cls: Any, r1: Any, r3: Any, flow2: dict[str, Any], target_fidelity: float) -> None:
    """Install BBPSSW only for swapped r1-r3 flow2 pairs."""

    _install_ep_rule(rule_cls, r1, _ep_action_request, _ep_condition_request, flow2["r1_slots"], target_fidelity, "r3")
    _install_ep_rule(rule_cls, r3, _ep_action_await, _ep_condition_await, flow2["r3_slots"], target_fidelity, "r1")


def _es_condition_a(memory_info: Any, manager: Any, args: dict[str, Any]) -> list[Any]:
    allowed_states = {"ENTANGLED", "PURIFIED"}
    if not (int(args["index_lower"]) <= memory_info.index <= int(args["index_upper"])):
        return []
    if memory_info.state not in allowed_states or memory_info.fidelity < float(args["target_fidelity"]):
        return []
    left, right = args["left"], args["right"]
    wanted = right if memory_info.remote_node == left else left if memory_info.remote_node == right else None
    if wanted is None:
        return []
    for info in manager:
        if info.state in allowed_states and int(args["index_lower"]) <= info.index <= int(args["index_upper"]):
            if info.remote_node == wanted and info.fidelity >= float(args["target_fidelity"]):
                return [memory_info, info]
    return []


def _es_condition_b(memory_info: Any, manager: Any, args: dict[str, Any]) -> list[Any]:
    allowed_states = {"ENTANGLED", "PURIFIED"}
    if memory_info.state in allowed_states and int(args["index_lower"]) <= memory_info.index <= int(args["index_upper"]):
        if memory_info.remote_node != args["target_node"] and memory_info.fidelity >= float(args["target_fidelity"]):
            return [memory_info]
    return []


def _es_match_func(protocols: list[Any], args: dict[str, Any]) -> Any:
    imports = _import_sequence(None)
    for protocol in protocols:
        if isinstance(protocol, imports.EntanglementSwappingB) and protocol.memory.name == args["target_memo"]:
            return protocol
    return None


def _es_action_a(memories_info: list[Any], args: dict[str, Any]) -> list[Any]:
    imports = _import_sequence(None)
    memories = [info.memory for info in memories_info]
    protocol = imports.EntanglementSwappingA.create(
        None,
        f"ESA.{memories[0].name}.{memories[1].name}",
        memories[0],
        memories[1],
        success_prob=float(args["succ_prob"]),
    )
    # SeQUeNCe's circuit swap protocol defaults to a 0.95 degradation factor.
    # This comparison supports ideal Bell-state swaps only, so override that
    # implementation default when the selected SeQUeNCe class exposes it.
    if hasattr(protocol, "degradation"):
        protocol.degradation = 1.0
    dsts = [info.remote_node for info in memories_info]
    req_args = [{"target_memo": memories_info[0].remote_memo}, {"target_memo": memories_info[1].remote_memo}]
    return [protocol, dsts, [_es_match_func, _es_match_func], req_args]


def _es_action_b(memories_info: list[Any], args: dict[str, Any]) -> list[Any]:
    imports = _import_sequence(None)
    memory = memories_info[0].memory
    protocol = imports.EntanglementSwappingB.create(None, "ESB." + memory.name, memory)
    return [protocol, [None], [None], [None]]


def _build_network(resolved: dict[str, Any], imports: SequenceImports, seed: int) -> tuple[Any, Any, Any, Any]:
    """Build the configured SeQUeNCe network and return timeline and routers."""

    derived = resolved["derived"]
    memories = resolved["memories"]
    detectors = resolved["detectors"]
    RouterNode = _make_router_class(imports, resolved)

    timeline = imports.Timeline(float(resolved["experiment"]["runtime_s"]) * 1e12)
    r1 = RouterNode("r1", timeline, int(memories["r1_count"]))
    r2 = RouterNode("r2", timeline, int(memories["r2_count"]))
    r3 = RouterNode("r3", timeline, int(memories["r3_count"]))

    detector_params = {
        "efficiency": float(detectors["efficiency"]),
        "dark_count": float(detectors["dark_count_rate_hz"]),
        "count_rate": float(detectors["count_rate_hz"]),
        "time_resolution": int(detectors["time_resolution_ps"]),
    }
    bsm_templates = {"SingleAtomBSM": {"detectors": [dict(detector_params), dict(detector_params)]}}
    m12 = imports.BSMNode("m12", timeline, ["r1", "r2"], component_templates=bsm_templates)
    m23 = imports.BSMNode("m23", timeline, ["r2", "r3"], component_templates=bsm_templates)
    nodes = [r1, r2, r3, m12, m23]
    for index, node in enumerate(nodes):
        node.set_seed(seed + index)

    for node1 in nodes:
        for node2 in nodes:
            cc = imports.ClassicalChannel(f"cc_{node1.name}_{node2.name}", timeline, 1e3, delay=int(derived["classical_delay_ps"]))
            cc.set_ends(node1, node2.name)

    for name, src, dst in (("qc_r1_m12", r1, m12), ("qc_r2_m12", r2, m12), ("qc_r2_m23", r2, m23), ("qc_r3_m23", r3, m23)):
        qc = imports.QuantumChannel(
            name,
            timeline,
            float(derived["sequence_quantum_attenuation_db_per_m"]),
            float(derived["half_link_m"]),
            frequency=float(resolved["optics"]["quantum_channel_frequency_hz"]),
        )
        qc.set_ends(src, dst.name)

    return timeline, r1, r2, r3


def _collect_pairs(simulator: str, seed: int, router: Any) -> list[dict[str, Any]]:
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


def _summary_row(
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


def run_sequence(config: dict[str, Any], seed: int, output_dir: str | pathlib.Path) -> dict[str, Any]:
    """Run SeQUeNCe from the shared config and write canonical outputs."""

    resolved = resolve_config(config)
    imports = _import_sequence(resolved["paths"].get("sequence_path"))
    timeline, r1, r2, r3 = _build_network(resolved, imports, seed)
    flow1 = resolved["resource_reservation"]["flow1"]
    flow2 = resolved["resource_reservation"]["flow2"]

    timeline.init()
    _install_eg_rule(imports.Rule, r1, _eg_action_request, "m12", "r2", flow1["r1_slots"], "r1", flow1["r2_slots"])
    _install_eg_rule(imports.Rule, r2, _eg_action_await, "m12", "r1", flow1["r2_slots"])
    _install_eg_rule(imports.Rule, r1, _eg_action_request, "m12", "r2", flow2["r1_slots"], "r1", flow2["r2_left_slots"])
    _install_eg_rule(imports.Rule, r2, _eg_action_await, "m12", "r1", flow2["r2_left_slots"])
    _install_eg_rule(imports.Rule, r2, _eg_action_request, "m23", "r3", flow2["r2_right_slots"], "r2", flow2["r3_slots"])
    _install_eg_rule(imports.Rule, r3, _eg_action_await, "m23", "r2", flow2["r3_slots"])

    target_fidelity = resolved["derived"]["target_purification_fidelity"]
    _install_end_to_end_ep_rules(imports.Rule, r1, r3, flow2, target_fidelity)

    r1.resource_manager.load(imports.Rule(
        10,
        _es_action_b,
        _es_condition_b,
        {},
        {"index_lower": flow2["r1_slots"][0], "index_upper": flow2["r1_slots"][1], "target_node": "r3", "target_fidelity": target_fidelity},
    ))
    r3.resource_manager.load(imports.Rule(
        10,
        _es_action_b,
        _es_condition_b,
        {},
        {"index_lower": flow2["r3_slots"][0], "index_upper": flow2["r3_slots"][1], "target_node": "r1", "target_fidelity": target_fidelity},
    ))
    r2.resource_manager.load(imports.Rule(
        10,
        _es_action_a,
        _es_condition_a,
        {"succ_prob": resolved["swapping"]["success_probability"]},
        {"index_lower": flow2["r2_left_slots"][0], "index_upper": flow2["r2_right_slots"][1], "target_fidelity": target_fidelity, "left": "r1", "right": "r3"},
    ))
    timeline.run()

    pairs = _collect_pairs("sequence", seed, r1)
    summary = _summary_row(
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
