"""Diagnostic SeQUeNCe runs for stage-by-stage timing attribution."""

from __future__ import annotations

import functools
import pathlib
from typing import Any

from sequence_qsavory_comparison.common.config import resolve_config
from sequence_qsavory_comparison.common.diagnostics import (
    DIAGNOSTIC_SCHEMA_VERSION,
    DiagnosticRecorder,
    scenario_config,
    summarize_events,
)
from sequence_qsavory_comparison.common.outputs import (
    ensure_output_dir,
    utc_now_iso,
    write_diagnostic_events_csv,
    write_diagnostic_stage_csv,
    write_manifest,
)

from .generation import eg_action_await, eg_action_request, install_eg_rule
from .imports import import_sequence
from .network import build_network
from .purification import install_end_to_end_ep_rules, install_werner_bbpssw_protocol
from .results import collect_pairs, summary_row
from .swapping import es_action_a, es_action_b, es_condition_a, es_condition_b


def run_sequence_diagnostic(
    config: dict[str, Any],
    *,
    seed: int,
    scenario: str,
    output_dir: str | pathlib.Path,
) -> dict[str, Any]:
    """Run one instrumented SeQUeNCe diagnostic scenario.

    Args:
        config: Shared configuration dictionary.
        seed: Deterministic simulator seed.
        scenario: Diagnostic scenario name from
            :mod:`sequence_qsavory_comparison.common.diagnostics`.
        output_dir: Directory receiving `events.csv`, `stage_summary.csv`, and
            `diagnostic_manifest.json`.

    Returns:
        In-memory manifest, events, stage summaries, pairs, and normal summary.
    """

    cfg = scenario_config(config, scenario)
    resolved = resolve_config(cfg)
    imports = import_sequence(resolved["paths"].get("sequence_path"))
    install_werner_bbpssw_protocol(imports)
    out = ensure_output_dir(output_dir)
    recorder = DiagnosticRecorder(
        simulator="sequence",
        seed=seed,
        scenario=scenario,
        link_length_km=float(resolved["topology"]["link_length_km"]),
    )

    timeline, r1, r2, r3 = build_network(resolved, imports, seed)
    _patch_resource_manager(imports, recorder)
    for node in (r1, r2, r3):
        node.resource_manager._diagnostic_recorder = recorder
    timeline.init()
    flow1 = resolved["resource_reservation"]["flow1"]
    flow2 = resolved["resource_reservation"]["flow2"]

    if scenario in {"single_lane_elementary", "same_link_multilane", "competing_flows_same_bsm", "full_reduced"}:
        _install_logged_eg(imports, recorder, r1, eg_action_request, "m12", "r2", flow1["r1_slots"], "flow1", "r1-r2", "r1", flow1["r2_slots"])
        _install_logged_eg(imports, recorder, r2, eg_action_await, "m12", "r1", flow1["r2_slots"], "flow1", "r1-r2")
    if scenario in {"competing_flows_same_bsm", "two_link_no_swap", "eg_swap_no_purification", "full_reduced"}:
        _install_logged_eg(imports, recorder, r1, eg_action_request, "m12", "r2", flow2["r1_slots"], "flow2_left", "r1-r2", "r1", flow2["r2_left_slots"])
        _install_logged_eg(imports, recorder, r2, eg_action_await, "m12", "r1", flow2["r2_left_slots"], "flow2_left", "r1-r2")
    if scenario in {"two_link_no_swap", "eg_swap_no_purification", "full_reduced"}:
        _install_logged_eg(imports, recorder, r2, eg_action_request, "m23", "r3", flow2["r2_right_slots"], "flow2_right", "r2-r3", "r2", flow2["r3_slots"])
        _install_logged_eg(imports, recorder, r3, eg_action_await, "m23", "r2", flow2["r3_slots"], "flow2_right", "r2-r3")

    if scenario in {"eg_swap_no_purification", "full_reduced"}:
        target_fidelity = resolved["derived"]["target_purification_fidelity"]
        r1.resource_manager.load(imports.Rule(10, _logged_action(recorder, es_action_b, "swap", "action_b"), es_condition_b, {}, {"index_lower": flow2["r1_slots"][0], "index_upper": flow2["r1_slots"][1], "target_node": "r3", "target_fidelity": target_fidelity}))
        r3.resource_manager.load(imports.Rule(10, _logged_action(recorder, es_action_b, "swap", "action_b"), es_condition_b, {}, {"index_lower": flow2["r3_slots"][0], "index_upper": flow2["r3_slots"][1], "target_node": "r1", "target_fidelity": target_fidelity}))
        r2.resource_manager.load(imports.Rule(10, _logged_action(recorder, es_action_a, "swap", "action_a"), es_condition_a, {"succ_prob": resolved["swapping"]["success_probability"]}, {"index_lower": flow2["r2_left_slots"][0], "index_upper": flow2["r2_right_slots"][1], "target_fidelity": target_fidelity, "left": "r1", "right": "r3"}))

    if scenario == "full_reduced" and bool(resolved["purification"]["enabled"]):
        install_end_to_end_ep_rules(imports.Rule, r1, r3, flow2, resolved["derived"]["target_purification_fidelity"])

    timeline.run()
    _log_elementary_memory_deliveries(recorder, r1, flow1["r1_slots"], "flow1", "r1-r2")
    _log_elementary_memory_deliveries(recorder, r1, flow2["r1_slots"], "flow2_left", "r1-r2")
    _log_elementary_memory_deliveries(recorder, r2, flow2["r2_right_slots"], "flow2_right", "r2-r3")
    pairs = collect_pairs("sequence", seed, r1)
    _log_pair_deliveries(recorder, pairs)
    stages = summarize_events(recorder.events)
    summary = summary_row(
        "sequence",
        seed,
        "completed",
        float(resolved["experiment"]["runtime_s"]),
        pairs,
        int(flow2["target_pairs"]),
        bool(resolved["purification"]["enabled"]),
    )
    manifest = {
        "schema_version": DIAGNOSTIC_SCHEMA_VERSION,
        "simulator": "sequence",
        "seed": seed,
        "scenario": scenario,
        "created_at": utc_now_iso(),
        "raw_config": cfg,
        "resolved_config": resolved,
        "outputs": {"events": "events.csv", "stage_summary": "stage_summary.csv", "manifest": "diagnostic_manifest.json"},
    }
    write_diagnostic_events_csv(out / "events.csv", recorder.events)
    write_diagnostic_stage_csv(out / "stage_summary.csv", stages)
    write_manifest(out / "diagnostic_manifest.json", manifest)
    return {"manifest": manifest, "events": recorder.events, "stage_summary": stages, "pairs": pairs, "summary": summary}


def _install_logged_eg(imports: Any, recorder: DiagnosticRecorder, node: Any, action: Any, mid: str, other: str, slot_range: list[int], flow: str, link: str, node_name: str | None = None, remote_range: list[int] | None = None) -> None:
    install_eg_rule(imports.Rule, node, _logged_eg_action(recorder, action, flow, link), mid, other, slot_range, node_name, remote_range)


def _logged_eg_action(recorder: DiagnosticRecorder, action: Any, flow: str, link: str) -> Any:
    @functools.wraps(action)
    def wrapper(memories_info: list[Any], args: dict[str, Any]) -> list[Any]:
        now = memories_info[0].memory.timeline.now() * 1e-12
        for info in memories_info:
            recorder.log(stage="resource", event="memory_reserved", time_s=now, flow=flow, link=link, node=info.memory.owner.name if hasattr(info.memory, "owner") else "", slot=info.index)
        payload = action(memories_info, args)
        protocol = payload[0]
        _instrument_eg_protocol(protocol, recorder, flow, link)
        return payload

    return wrapper


def _logged_action(recorder: DiagnosticRecorder, action: Any, stage: str, event: str) -> Any:
    @functools.wraps(action)
    def wrapper(memories_info: list[Any], args: dict[str, Any]) -> list[Any]:
        now = memories_info[0].memory.timeline.now() * 1e-12
        for info in memories_info:
            recorder.log(stage=stage, event=event, time_s=now, node=getattr(info.memory.owner, "name", ""), slot=info.index, details={"remote_node": getattr(info, "remote_node", "")})
        return action(memories_info, args)

    return wrapper


def _instrument_eg_protocol(protocol: Any, recorder: DiagnosticRecorder, flow: str, link: str) -> None:
    original_start = protocol.start
    original_update = protocol.update_memory
    original_received = protocol.received_message

    def start_wrapper() -> Any:
        recorder.log(stage="barrett_kok", event="start", time_s=protocol.owner.timeline.now() * 1e-12, flow=flow, link=link, node=protocol.owner.name, slot=_slot_index(protocol), details={"round": getattr(protocol, "ent_round", "") + 1})
        return original_start()

    def update_wrapper() -> Any:
        before = getattr(protocol, "ent_round", "")
        result = original_update()
        event = "round_update"
        if result is True and getattr(protocol, "ent_round", None) == 3:
            event = "success"
        elif result is False:
            event = "failure"
        recorder.log(stage="barrett_kok", event=event, time_s=protocol.owner.timeline.now() * 1e-12, flow=flow, link=link, node=protocol.owner.name, slot=_slot_index(protocol), details={"round_before": before, "round_after": getattr(protocol, "ent_round", ""), "result": result})
        return result

    def received_wrapper(src: str, msg: Any) -> Any:
        recorder.log(stage="barrett_kok", event=f"message_{getattr(msg.msg_type, 'name', msg.msg_type)}", time_s=protocol.owner.timeline.now() * 1e-12, flow=flow, link=link, node=protocol.owner.name, slot=_slot_index(protocol), details={"src": src, "expected_time_ps": getattr(protocol, "expected_time", "")})
        return original_received(src, msg)

    protocol.start = start_wrapper
    protocol.update_memory = update_wrapper
    protocol.received_message = received_wrapper


def _patch_resource_manager(imports: Any, recorder: DiagnosticRecorder) -> None:
    cls = imports.ResourceManager
    if getattr(cls, "_qsavory_diag_patched", False):
        return
    original_send_request = cls.send_request
    original_received = cls.received_message

    def send_request(self: Any, protocol: Any, req_dst: str | None, req_condition_func: Any, req_args: Any) -> Any:
        active = getattr(self, "_diagnostic_recorder", None)
        if active is not None:
            active.log(stage="resource", event="request_sent" if req_dst is not None else "await_registered", time_s=self.owner.timeline.now() * 1e-12, node=self.owner.name, details={"protocol": protocol.name, "dst": req_dst})
        return original_send_request(self, protocol, req_dst, req_condition_func, req_args)

    def received_message(self: Any, src: str, msg: Any) -> Any:
        active = getattr(self, "_diagnostic_recorder", None)
        if active is not None:
            active.log(stage="resource", event=f"message_{getattr(msg.msg_type, 'name', msg.msg_type)}", time_s=self.owner.timeline.now() * 1e-12, node=self.owner.name, details={"src": src, "protocol": getattr(msg, "protocol", "")})
        return original_received(self, src, msg)

    cls.send_request = send_request
    cls.received_message = received_message
    cls._qsavory_diag_patched = True


def _slot_index(protocol: Any) -> int | str:
    try:
        return protocol.memory.memory_array.memories.index(protocol.memory)
    except Exception:
        return ""


def _log_pair_deliveries(recorder: DiagnosticRecorder, pairs: list[dict[str, Any]]) -> None:
    for pair in pairs:
        time_s = float(pair["delivery_time_s"])
        flow = str(pair["flow"])
        link = f'{pair["local_node"]}-{pair["remote_node"]}'
        status = pair.get("status", "")
        details = {"status": status, "fidelity": pair.get("fidelity", "")}
        recorder.log(stage="pair", event="delivered", time_s=time_s, flow=flow, link=link, node=str(pair["local_node"]), slot=pair["local_slot"], pair_id=pair["pair_id"], details=details)
        if flow == "flow2":
            recorder.log(stage="swapped_delivered", event="delivered", time_s=time_s, flow=flow, link="r1-r3", node=str(pair["local_node"]), slot=pair["local_slot"], pair_id=pair["pair_id"], details=details)
            if status == "PURIFIED":
                recorder.log(stage="bbpssw_completed", event="completed", time_s=time_s, flow=flow, link="r1-r3", node=str(pair["local_node"]), slot=pair["local_slot"], pair_id=pair["pair_id"], details=details)


def _log_elementary_memory_deliveries(recorder: DiagnosticRecorder, node: Any, slot_range: list[int], flow: str, link: str) -> None:
    for index in range(int(slot_range[0]), int(slot_range[1]) + 1):
        info = node.resource_manager.memory_manager[index]
        if info.state not in {"ENTANGLED", "PURIFIED"} or info.entangle_time <= 0:
            continue
        recorder.log(
            stage="elementary_delivered",
            event="delivered",
            time_s=info.entangle_time * 1e-12,
            flow=flow,
            link=link,
            node=node.name,
            slot=index,
            pair_id=getattr(info, "remote_memo", ""),
            details={"status": info.state, "remote_node": info.remote_node, "fidelity": info.fidelity},
        )
