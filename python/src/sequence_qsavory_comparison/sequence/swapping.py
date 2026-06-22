"""SeQUeNCe entanglement-swapping rules.

The comparison uses ideal Bell-state swaps.  SeQUeNCe's stock swapping
protocol may expose a degradation factor, and the request-side action overrides
that factor to ``1.0`` so the Python and Julia implementations use the same
state-transform semantics.
"""

from __future__ import annotations

from typing import Any

from .imports import import_sequence


def es_condition_a(memory_info: Any, manager: Any, args: dict[str, Any]) -> list[Any]:
    """Select two middle-node memories for an ``r1-r3`` swap.

    Args:
        memory_info: Candidate memory at the middle router.
        manager: Middle-router memory manager used to find the opposite-link
            pair.
        args: Rule arguments containing inclusive slot bounds,
            ``target_fidelity``, and endpoint names ``left`` and ``right``.

    Returns:
        Two compatible ``MemoryInfo`` records, one connected to each endpoint,
        or an empty list.
    """

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


def es_condition_b(memory_info: Any, manager: Any, args: dict[str, Any]) -> list[Any]:
    """Select one endpoint memory waiting for a swap notification.

    Args:
        memory_info: Candidate endpoint memory.
        manager: Endpoint memory manager, unused here but present in the
            SeQUeNCe callback signature.
        args: Rule arguments containing local slot bounds, ``target_node``,
            and ``target_fidelity``.

    Returns:
        ``[memory_info]`` when the endpoint memory can participate in a swap,
        otherwise an empty list.
    """

    allowed_states = {"ENTANGLED", "PURIFIED"}
    if memory_info.state in allowed_states and int(args["index_lower"]) <= memory_info.index <= int(args["index_upper"]):
        if memory_info.remote_node != args["target_node"] and memory_info.fidelity >= float(args["target_fidelity"]):
            return [memory_info]
    return []


def es_match_func(protocols: list[Any], args: dict[str, Any]) -> Any:
    """Find the endpoint ``EntanglementSwappingB`` protocol by memory name.

    Args:
        protocols: Candidate endpoint protocols offered by the remote rule
            manager.
        args: Dictionary with ``target_memo``, the endpoint memory name.

    Returns:
        A matching endpoint protocol, or ``None`` if it is not ready.
    """

    imports = import_sequence(None)
    for protocol in protocols:
        if isinstance(protocol, imports.EntanglementSwappingB) and protocol.memory.name == args["target_memo"]:
            return protocol
    return None


def es_action_a(memories_info: list[Any], args: dict[str, Any]) -> list[Any]:
    """Create the middle-node swap protocol and remote match requests.

    Args:
        memories_info: Two middle-node memory records selected by
            :func:`es_condition_a`.
        args: Action arguments containing ``succ_prob``.

    Returns:
        The SeQUeNCe action payload that creates ``EntanglementSwappingA`` at
        the middle node and asks both endpoints to match by remote memory name.
    """

    imports = import_sequence(None)
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
    return [protocol, dsts, [es_match_func, es_match_func], req_args]


def es_action_b(memories_info: list[Any], args: dict[str, Any]) -> list[Any]:
    """Create an endpoint swap protocol for one memory.

    Args:
        memories_info: One endpoint memory record.
        args: Unused action dictionary required by SeQUeNCe's callback shape.

    Returns:
        A SeQUeNCe action payload with no outbound protocol request.
    """

    imports = import_sequence(None)
    memory = memories_info[0].memory
    protocol = imports.EntanglementSwappingB.create(None, "ESB." + memory.name, memory)
    return [protocol, [None], [None], [None]]


_es_condition_a = es_condition_a
_es_condition_b = es_condition_b
_es_match_func = es_match_func
_es_action_a = es_action_a
_es_action_b = es_action_b
