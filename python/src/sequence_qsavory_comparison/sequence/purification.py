"""SeQUeNCe BBPSSW purification rules.

The comparison purifies only swapped end-to-end ``r1-r3`` pairs.  Elementary
``r1-r2`` and ``r2-r3`` pairs are left untouched so both simulators implement
the same resource-management semantics.
"""

from __future__ import annotations

from typing import Any

from .imports import import_sequence


def ep_condition_request(memory_info: Any, manager: Any, args: dict[str, Any]) -> list[Any]:
    """Select two same-fidelity entangled pairs for request-side BBPSSW.

    Args:
        memory_info: Candidate kept pair on the request node.
        manager: SeQUeNCe memory manager used to find a second compatible pair.
        args: Rule arguments containing slot bounds, ``target_fidelity``, and
            optionally ``remote_node``.

    Returns:
        Two ``MemoryInfo`` objects when BBPSSW can start locally, otherwise an
        empty list.
    """

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


def ep_condition_await(memory_info: Any, manager: Any, args: dict[str, Any]) -> list[Any]:
    """Select one remote endpoint memory waiting for BBPSSW matching.

    Args:
        memory_info: Candidate memory on the response node.
        manager: SeQUeNCe memory manager, unused here but required by the rule
            callback signature.
        args: Rule arguments containing slot bounds, ``target_fidelity``, and
            optionally ``remote_node``.

    Returns:
        ``[memory_info]`` when the memory is an eligible low-fidelity
        entangled pair, otherwise an empty list.
    """

    if int(args["index_lower"]) <= memory_info.index <= int(args["index_upper"]):
        remote_node = args.get("remote_node")
        if remote_node is not None and memory_info.remote_node != remote_node:
            return []
        if memory_info.state == "ENTANGLED" and memory_info.fidelity < float(args["target_fidelity"]):
            return [memory_info]
    return []


def ep_match_func(protocols: list[Any], args: dict[str, Any]) -> Any:
    """Match two remote BBPSSW endpoint protocols into one response protocol.

    SeQUeNCe creates one await-side protocol per remote memory.  The
    request-side action sends the names of the two remote memories, and this
    function combines those await-side protocols so the remote node mirrors the
    local two-memory BBPSSW instance.

    Args:
        protocols: Candidate BBPSSW protocols on the response node.
        args: Dictionary with ``remote1`` and ``remote2`` memory names.

    Returns:
        The combined response-side ``BBPSSWProtocol``, or ``None`` when both
        remote memories are not yet represented.
    """

    imports = import_sequence(None)
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


def ep_action_request(memories_info: list[Any], args: dict[str, Any]) -> list[Any]:
    """Create the request-side BBPSSW protocol for two local memories.

    Args:
        memories_info: Two same-fidelity memory records selected by
            :func:`ep_condition_request`.
        args: Unused action dictionary required by SeQUeNCe's callback shape.

    Returns:
        The SeQUeNCe action payload that requests a matching protocol on the
        remote endpoint.
    """

    imports = import_sequence(None)
    memories = [info.memory for info in memories_info]
    protocol = imports.BBPSSWProtocol.create(None, f"EP.{memories[0].name}.{memories[1].name}", memories[0], memories[1])
    req_args = {"remote1": memories_info[0].remote_memo, "remote2": memories_info[1].remote_memo}
    return [protocol, [memories_info[0].remote_node], [ep_match_func], [req_args]]


def ep_action_await(memories_info: list[Any], args: dict[str, Any]) -> list[Any]:
    """Create an await-side BBPSSW protocol for one remote memory.

    Args:
        memories_info: One response-side memory record.
        args: Unused action dictionary required by SeQUeNCe's callback shape.

    Returns:
        A SeQUeNCe action payload with no outbound request.
    """

    imports = import_sequence(None)
    memory = memories_info[0].memory
    protocol = imports.BBPSSWProtocol.create(None, "EP." + memory.name, memory, None)
    return [protocol, [None], [None], [None]]


def install_ep_rule(rule_cls: Any, node: Any, action: Any, condition: Any, slot_range: list[int], target_fidelity: float, remote_node: str | None = None) -> None:
    """Install one BBPSSW rule on a router node.

    Args:
        rule_cls: SeQUeNCe ``Rule`` class.
        node: Router node whose resource manager receives the rule.
        action: Request-side or await-side BBPSSW action callback.
        condition: Matching condition callback for the selected side.
        slot_range: Inclusive local memory range where purification is allowed.
        target_fidelity: Pairs at or above this fidelity are not purified.
        remote_node: Optional remote endpoint filter.
    """

    args = {"index_lower": slot_range[0], "index_upper": slot_range[1], "target_fidelity": target_fidelity}
    if remote_node is not None:
        args["remote_node"] = remote_node
    node.resource_manager.load(rule_cls(10, action, condition, {}, args))


def install_end_to_end_ep_rules(rule_cls: Any, r1: Any, r3: Any, flow2: dict[str, Any], target_fidelity: float) -> None:
    """Install BBPSSW only for swapped ``r1-r3`` flow-2 pairs.

    Args:
        rule_cls: SeQUeNCe ``Rule`` class.
        r1: Left endpoint router.
        r3: Right endpoint router.
        flow2: Shared config reservation block for the long-range flow.
        target_fidelity: Fidelity threshold at which end-to-end pairs are
            considered purified enough for the completion criterion.
    """

    install_ep_rule(rule_cls, r1, ep_action_request, ep_condition_request, flow2["r1_slots"], target_fidelity, "r3")
    install_ep_rule(rule_cls, r3, ep_action_await, ep_condition_await, flow2["r3_slots"], target_fidelity, "r1")


_ep_condition_request = ep_condition_request
_ep_condition_await = ep_condition_await
_ep_match_func = ep_match_func
_ep_action_request = ep_action_request
_ep_action_await = ep_action_await
_install_ep_rule = install_ep_rule
_install_end_to_end_ep_rules = install_end_to_end_ep_rules
