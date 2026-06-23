"""Lazy imports for SeQUeNCe symbols used by the adapter.

The Python package can be imported in environments where SeQUeNCe itself is not
installed, for example when only the plotting or shared-configuration helpers
are needed.  This module keeps SeQUeNCe imports behind an explicit function so
callers fail only when they request the Python simulator adapter.
"""

from __future__ import annotations

import pathlib
import sys
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SequenceImports:
    """Container for the SeQUeNCe classes used by this adapter.

    Attributes:
        Timeline: SeQUeNCe discrete-event timeline class.
        QuantumRouter: Router node class that owns memory arrays and protocol
            stacks.
        BSMNode: Midpoint Bell-state-measurement node class.
        ClassicalChannel: Classical channel class used for protocol messages.
        QuantumChannel: Quantum channel class used for photons.
        Rule: Resource-manager rule class.
        ResourceManager: Resource manager installed on comparison router nodes.
        MemoryInfo: Metadata record for one physical memory.
        EntanglementGenerationA: Barrett-Kok endpoint protocol.
        BBPSSWProtocol: SeQUeNCe BBPSSW purification protocol.
        EntanglementSwappingA: Swapping protocol run at the middle router.
        EntanglementSwappingB: Swapping protocol run at endpoint routers.
        BELL_DIAGONAL_STATE_FORMALISM: SeQUeNCe formalism identifier used for
            Werner/Bell-diagonal state tracking.
    """

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
    BELL_DIAGONAL_STATE_FORMALISM: str


def import_sequence(sequence_path: str | None = None) -> SequenceImports:
    """Import SeQUeNCe symbols from an installed package or local checkout.

    Args:
        sequence_path: Optional path to a SeQUeNCe source checkout.  When
            provided, the resolved path is prepended to ``sys.path`` before
            importing.  This lets the adapter use the vendored release copy
            without requiring a package installation step.

    Returns:
        A :class:`SequenceImports` bundle containing the SeQUeNCe classes used
        by the comparison implementation.

    Raises:
        ImportError: If SeQUeNCe is not importable from either ``sequence_path``
            or the active Python environment.

    Example:
        >>> imports = import_sequence("../dev/SeQUeNCe")
        >>> imports.Timeline is not None
        True
    """

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
    from sequence.constants import BELL_DIAGONAL_STATE_FORMALISM

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
        BELL_DIAGONAL_STATE_FORMALISM,
    )


_import_sequence = import_sequence
