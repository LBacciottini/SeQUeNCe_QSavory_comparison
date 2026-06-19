"""Lazy imports for SeQUeNCe symbols used by the adapter."""

from __future__ import annotations

import pathlib
import sys
from dataclasses import dataclass
from typing import Any


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


def import_sequence(sequence_path: str | None = None) -> SequenceImports:
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


_import_sequence = import_sequence
