"""SeQUeNCe network construction for the comparison scenario.

The adapter builds the three-router, two-midpoint topology from the shared
configuration and installs only hardware-level parameters here.  Protocol rules
are added later by :mod:`sequence_qsavory_comparison.sequence.simulation` so the
network setup remains separable from resource-management policy.
"""

from __future__ import annotations

from typing import Any

from .imports import SequenceImports


def make_router_class(imports: SequenceImports, resolved: dict[str, Any]):
    """Create a ``QuantumRouter`` subclass bound to one resolved config.

    The subclass sets memory-array parameters to the shared raw-fidelity,
    excitation-frequency, and source-efficiency values, disables memory
    decoherence/cutoff, and routes SeQUeNCe protocol messages to either the
    resource manager or the named protocol instance.

    Args:
        imports: Bundle of SeQUeNCe classes returned by
            :func:`sequence_qsavory_comparison.sequence.imports.import_sequence`.
        resolved: Shared config after :func:`resolve_config`, including the
            ``derived`` table.

    Returns:
        A router class ready to instantiate ``r1``, ``r2``, and ``r3``.
    """

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


def build_network(resolved: dict[str, Any], imports: SequenceImports, seed: int) -> tuple[Any, Any, Any, Any]:
    """Build the configured SeQUeNCe network and return timeline and routers.

    Args:
        resolved: Shared config after validation and derived-parameter
            computation.
        imports: Bundle of SeQUeNCe classes used to avoid module-level
            SeQUeNCe imports.
        seed: Base seed used to seed routers and midpoint BSM nodes
            deterministically.

    Returns:
        ``(timeline, r1, r2, r3)``.  The midpoint nodes and channels are owned
        by the SeQUeNCe timeline through component references and do not need to
        be returned to the caller.

    Example:
        >>> resolved = resolve_config(cfg)  # doctest: +SKIP
        >>> imports = import_sequence(resolved["paths"]["sequence_path"])  # doctest: +SKIP
        >>> timeline, r1, r2, r3 = build_network(resolved, imports, seed=1)  # doctest: +SKIP
    """

    derived = resolved["derived"]
    memories = resolved["memories"]
    detectors = resolved["detectors"]
    RouterNode = make_router_class(imports, resolved)

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


_make_router_class = make_router_class
_build_network = build_network
