"""SeQUeNCe elementary entanglement-generation rules."""

from __future__ import annotations

from typing import Any

from .imports import import_sequence


def rule_condition_raw(memory_info: Any, manager: Any, args: dict[str, Any]) -> list[Any]:
    if memory_info.state == "RAW" and int(args["index_lower"]) <= memory_info.index <= int(args["index_upper"]):
        return [memory_info]
    return []


def eg_match_func(protocols: list[Any], args: dict[str, Any]) -> Any:
    imports = import_sequence(None)
    for protocol in protocols:
        if not isinstance(protocol, imports.EntanglementGenerationA):
            continue
        memory_array = protocol.owner.get_components_by_type("MemoryArray")[0]
        if protocol.remote_node_name == args["remote_node"]:
            idx = memory_array.memories.index(protocol.memory)
            if int(args["index_lower"]) <= idx <= int(args["index_upper"]):
                return protocol
    return None


def eg_action_request(memories_info: list[Any], args: dict[str, Any]) -> list[Any]:
    imports = import_sequence(None)
    memory = memories_info[0].memory
    protocol = imports.EntanglementGenerationA.create(None, "EGA." + memory.name, args["mid_name"], args["other_name"], memory)
    req_args = {
        "remote_node": args["node_name"],
        "index_upper": args["index_upper"],
        "index_lower": args["index_lower"],
    }
    return [protocol, [args["other_name"]], [eg_match_func], [req_args]]


def eg_action_await(memories_info: list[Any], args: dict[str, Any]) -> list[Any]:
    imports = import_sequence(None)
    memory = memories_info[0].memory
    protocol = imports.EntanglementGenerationA.create(None, "EGA." + memory.name, args["mid_name"], args["other_name"], memory)
    return [protocol, [None], [None], [None]]


def install_eg_rule(rule_cls: Any, node: Any, action: Any, mid: str, other: str, slot_range: list[int], node_name: str | None = None, remote_range: list[int] | None = None) -> None:
    action_args = {"mid_name": mid, "other_name": other}
    if node_name is not None and remote_range is not None:
        action_args.update({"node_name": node_name, "index_lower": remote_range[0], "index_upper": remote_range[1]})
    condition_args = {"index_lower": slot_range[0], "index_upper": slot_range[1]}
    node.resource_manager.load(rule_cls(10, action, rule_condition_raw, action_args, condition_args))


_rule_condition_raw = rule_condition_raw
_eg_match_func = eg_match_func
_eg_action_request = eg_action_request
_eg_action_await = eg_action_await
_install_eg_rule = install_eg_rule
