"""SeQUeNCe elementary entanglement-generation rules.

The helpers in this module are intentionally small wrappers around SeQUeNCe's
resource-manager rule API.  A rule condition chooses eligible raw memories from
an inclusive slot range, while an action creates the corresponding
``EntanglementGenerationA`` endpoint protocol and, for request-side rules,
describes how the remote endpoint should be matched.
"""

from __future__ import annotations

from typing import Any

from .imports import import_sequence


def rule_condition_raw(memory_info: Any, manager: Any, args: dict[str, Any]) -> list[Any]:
    """Select one raw memory inside a reserved inclusive slot range.

    Args:
        memory_info: SeQUeNCe ``MemoryInfo`` object inspected by the rule
            manager.
        manager: Memory manager iterable.  It is unused for this single-memory
            condition but is part of SeQUeNCe's rule callback signature.
        args: Dictionary containing ``index_lower`` and ``index_upper``.

    Returns:
        ``[memory_info]`` when the memory is raw and in range, otherwise an
        empty list.
    """

    if memory_info.state == "RAW" and int(args["index_lower"]) <= memory_info.index <= int(args["index_upper"]):
        return [memory_info]
    return []


def eg_match_func(protocols: list[Any], args: dict[str, Any]) -> Any:
    """Find the remote Barrett-Kok endpoint protocol for a request.

    Args:
        protocols: Candidate protocols offered by SeQUeNCe's rule manager on
            the remote node.
        args: Matching dictionary with ``remote_node``, ``index_lower``, and
            ``index_upper`` describing the requester and the remote reserved
            range.

    Returns:
        The matching ``EntanglementGenerationA`` protocol, or ``None`` if no
        compatible protocol has been created yet.
    """

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
    """Create the request-side Barrett-Kok endpoint protocol.

    Args:
        memories_info: One selected local memory from
            :func:`rule_condition_raw`.
        args: Rule action arguments containing ``mid_name``, ``other_name``,
            ``node_name``, and the remote slot range used by
            :func:`eg_match_func`.

    Returns:
        The four-element SeQUeNCe action payload:
        ``[local_protocol, remote_nodes, match_functions, match_args]``.
    """

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
    """Create the await-side Barrett-Kok endpoint protocol.

    Args:
        memories_info: One selected local memory.
        args: Rule action arguments containing ``mid_name`` and ``other_name``.

    Returns:
        A SeQUeNCe action payload with no outbound protocol request.  The
        request-side rule matches this protocol later.
    """

    imports = import_sequence(None)
    memory = memories_info[0].memory
    protocol = imports.EntanglementGenerationA.create(None, "EGA." + memory.name, args["mid_name"], args["other_name"], memory)
    return [protocol, [None], [None], [None]]


def install_eg_rule(rule_cls: Any, node: Any, action: Any, mid: str, other: str, slot_range: list[int], node_name: str | None = None, remote_range: list[int] | None = None) -> None:
    """Install one elementary-generation rule on a router node.

    Args:
        rule_cls: SeQUeNCe ``Rule`` class.
        node: Router node whose resource manager receives the rule.
        action: Either :func:`eg_action_request` or :func:`eg_action_await`.
        mid: Name of the midpoint BSM node.
        other: Name of the remote router endpoint.
        slot_range: Inclusive local memory range owned by this flow.
        node_name: Local node name advertised to the remote matcher.  Required
            only for request-side rules.
        remote_range: Inclusive remote memory range expected by the matcher.
            Required only for request-side rules.
    """

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
