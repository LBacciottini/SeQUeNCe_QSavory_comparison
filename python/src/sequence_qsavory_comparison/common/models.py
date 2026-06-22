"""Simulator-agnostic physical formulas used by both adapters.

This module is deliberately free of simulator imports. It is the single Python
source of truth for link-level derived parameters, so tests can detect when an
adapter silently uses a different convention.
"""

from __future__ import annotations

import math
from math import isfinite
from typing import Any

PS_PER_SECOND = 1_000_000_000_000


def _require_probability(name: str, value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be in [0, 1], got {value!r}")


def barrett_kok_fidelity_symmetric(eta: float, eta_d: float, visibility: float, dark_prob: float) -> float:
    """Return the symmetric Barrett-Kok Bell-state fidelity.

    The formula matches the `BarrettKokBellPair` state used on the
    QuantumSavory side for parity bit `m=0`, and is used on the SeQUeNCe side
    as the raw memory fidelity configured for generated pairs.

    Args:
        eta: One-arm optical transmissivity from memory emission through fiber
            to the BSM input.
        eta_d: Detector efficiency.
        visibility: Mode-matching visibility in the interference term.
        dark_prob: Excess detector click probability per modeled detection
            opportunity.

    Returns:
        Bell-state fidelity for the symmetric Barrett-Kok raw state. Returns
        `nan` when the denominator is zero.

    Raises:
        ValueError: If any probability-like argument is outside `[0, 1]`.

    Example:
        ```python
        fidelity = barrett_kok_fidelity_symmetric(
            eta=0.6,
            eta_d=0.9,
            visibility=0.99,
            dark_prob=1e-8,
        )
        ```
    """

    for name, value in (
        ("eta", eta),
        ("eta_d", eta_d),
        ("visibility", visibility),
        ("dark_prob", dark_prob),
    ):
        _require_probability(name, value)

    d1_0 = eta * eta * eta_d * eta_d / 4.0
    d3_0 = d1_0 * visibility * visibility
    d1_1 = (1.0 - dark_prob) * eta_d * (2.0 * eta - 2.0 * eta * eta * eta_d)
    d1_1 += dark_prob * (1.0 - eta * eta_d) * (1.0 - eta * eta_d)

    numerator = (1.0 - dark_prob) ** 4 * (d1_0 + d3_0)
    numerator += dark_prob * (1.0 - dark_prob) ** 2 * d1_1
    denominator = 2.0 * (1.0 - dark_prob) ** 4 * d1_0
    denominator += 4.0 * dark_prob * (1.0 - dark_prob) ** 2 * d1_1
    return numerator / denominator if denominator else float("nan")


def _schedule_sequence_transmit_ps(min_time_ps: int, frequency_hz: float) -> int:
    """Mirror SeQUeNCe `QuantumChannel.schedule_transmit` bin selection.

    SeQUeNCe converts the requested picosecond time to the next available
    quantum-channel clock bin, then converts the integer bin back to an integer
    picosecond timestamp. The elementary validation uses one photon on one
    channel per round, so the selected bin is never already occupied.

    Args:
        min_time_ps: Earliest allowed transmit time in picoseconds.
        frequency_hz: Quantum-channel clock frequency.

    Returns:
        Scheduled transmit time in picoseconds.
    """

    time_bin = min_time_ps * frequency_hz / PS_PER_SECOND
    rounded_bin = math.ceil(time_bin - 1e-12)
    return int(rounded_bin * PS_PER_SECOND / frequency_hz)


def _sequence_barrett_kok_timing(
    *,
    quantum_delay_ps: int,
    classical_delay_ps: int,
    quantum_channel_frequency_hz: float,
    memory_frequency_hz: float,
    protocol_gap_ps: int,
) -> dict[str, Any]:
    """Return the SeQUeNCe-derived timing of one logical BK attempt.

    This follows the actual SeQUeNCe source path used by the adapter:

    - resource-manager `REQUEST` travels from the requester to the responder;
    - the responder starts as Barrett-Kok primary and sends `NEGOTIATE`;
    - the non-primary schedules each photon with `QuantumChannel.schedule_transmit`;
    - the next BK round is scheduled after midpoint result return plus the
      hardcoded protocol gap.

    The current adapter is symmetric: both endpoint-to-endpoint and
    endpoint-to-midpoint classical channels use `classical_delay_ps`, and both
    quantum arms use `quantum_delay_ps`.

    Args:
        quantum_delay_ps: One-way endpoint-to-midpoint photon delay.
        classical_delay_ps: Classical control-message delay used by the
            SeQUeNCe adapter.
        quantum_channel_frequency_hz: Quantum-channel scheduling frequency.
        memory_frequency_hz: Memory excitation frequency.
        protocol_gap_ps: SeQUeNCe Barrett-Kok gap after BSM result return.

    Returns:
        Dictionary of picosecond timing milestones used to derive the
        compressed QuantumSavory attempt duration.
    """

    primary_start_ps = classical_delay_ps
    nonprimary_start_ps = 2 * classical_delay_ps
    memory_period_ps = int(PS_PER_SECOND / memory_frequency_hz)
    next_excite_ps = 0

    round1_min_emit_ps = max(nonprimary_start_ps, next_excite_ps) + classical_delay_ps
    round1_emit_ps = _schedule_sequence_transmit_ps(round1_min_emit_ps, quantum_channel_frequency_hz)
    round1_done_ps = round1_emit_ps + quantum_delay_ps + classical_delay_ps + protocol_gap_ps
    next_excite_ps = round1_emit_ps + memory_period_ps

    round2_start_ps = round1_done_ps
    round2_negotiate_arrival_ps = round2_start_ps + classical_delay_ps
    round2_min_emit_ps = max(round2_negotiate_arrival_ps, next_excite_ps) + classical_delay_ps
    round2_emit_ps = _schedule_sequence_transmit_ps(round2_min_emit_ps, quantum_channel_frequency_hz)
    round2_done_ps = round2_emit_ps + quantum_delay_ps + classical_delay_ps + protocol_gap_ps

    return {
        "resource_request_arrival_ps": primary_start_ps,
        "protocol_start_primary_ps": primary_start_ps,
        "protocol_start_nonprimary_ps": nonprimary_start_ps,
        "memory_period_ps": memory_period_ps,
        "round1_min_emit_ps": round1_min_emit_ps,
        "round1_emit_ps": round1_emit_ps,
        "round1_failure_time_ps": round1_done_ps,
        "round2_min_emit_ps": round2_min_emit_ps,
        "round2_emit_ps": round2_emit_ps,
        "two_round_time_ps": round2_done_ps,
        "round2_increment_time_ps": round2_done_ps - round1_done_ps,
    }


def derive_parameters(config: dict[str, Any]) -> dict[str, Any]:
    """Compute simulator-agnostic derived parameters from a validated config.

    The returned dictionary is stored in manifests as `resolved_config.derived`
    and is the shared source for simulator-specific adapters. It includes
    optical transmissivities, detector click probabilities, Barrett-Kok success
    probability, raw fidelity, SeQUeNCe-derived timing milestones, and the
    purification target fidelity.

    Args:
        config: Validated shared configuration dictionary.

    Returns:
        Dictionary of derived scalar values. Seconds are used by default;
        fields ending in `_ps` are picoseconds, and attenuation values state
        their unit in the key.

    Example:
        ```python
        resolved = resolve_config(load_config("shared/configs/default.toml"))
        expected_rate = resolved["derived"]["barrett_kok_expected_rate_hz"]
        ```
    """

    topology = config["topology"]
    memories = config["memories"]
    optics = config["optics"]
    detectors = config["detectors"]
    bk = config["barrett_kok"]
    purification = config["purification"]

    link_length_km = float(topology["link_length_km"])
    speed_km_per_s = float(topology["signal_speed_km_per_s"])
    attenuation_db_per_km = float(optics["attenuation_db_per_km"])
    half_link_km = link_length_km / 2.0
    half_link_m = half_link_km * 1000.0

    fiber_transmissivity_half_link = 10.0 ** (-(attenuation_db_per_km * half_link_km) / 10.0)
    source_transmissivity = (
        float(memories["emission_efficiency"])
        * float(optics["collection_efficiency"])
        * float(optics["frequency_conversion_efficiency"])
    )
    arm_transmissivity = source_transmissivity * fiber_transmissivity_half_link
    detector_efficiency = float(detectors["efficiency"])
    dark_prob = float(detectors["dark_count_probability"])
    p_det_signal = arm_transmissivity * detector_efficiency
    p_det = p_det_signal + dark_prob - p_det_signal * dark_prob
    bk_success_probability = 0.5 * p_det * p_det
    bk_round2_entry_probability = math.sqrt(bk_success_probability)

    quantum_delay_s = half_link_km / speed_km_per_s
    classical_delay_s = link_length_km / speed_km_per_s
    quantum_delay_ps = int(round(quantum_delay_s * 1e12))
    classical_delay_ps = int(round(classical_delay_s * 1e12))

    excitation_time_s = float(memories["excitation_time_s"])
    memory_frequency_hz = 1.0 / max(excitation_time_s, 1e-12)
    protocol_gap_ps = int(bk["protocol_gap_ps"])
    bk_timing = _sequence_barrett_kok_timing(
        quantum_delay_ps=quantum_delay_ps,
        classical_delay_ps=classical_delay_ps,
        quantum_channel_frequency_hz=float(optics["quantum_channel_frequency_hz"]),
        memory_frequency_hz=memory_frequency_hz,
        protocol_gap_ps=protocol_gap_ps,
    )
    bk_round1_time_s = bk_timing["round1_failure_time_ps"] * 1e-12
    bk_round2_time_s = bk_timing["round2_increment_time_ps"] * 1e-12
    bk_two_round_time_s = bk_timing["two_round_time_ps"] * 1e-12
    bk_effective_attempt_time_s = bk_round1_time_s + bk_round2_entry_probability * bk_round2_time_s
    bk_expected_rate_hz = bk_success_probability / bk_effective_attempt_time_s

    raw_fidelity = barrett_kok_fidelity_symmetric(
        arm_transmissivity,
        detector_efficiency,
        float(bk["mode_matching_visibility"]),
        dark_prob,
    )
    if purification["target_fidelity_policy"] == "raw_squared_plus_margin":
        target_purification_fidelity = raw_fidelity * raw_fidelity + float(purification["target_fidelity_margin"])
    else:
        target_purification_fidelity = float(purification["target_fidelity_margin"])

    return {
        "units": {
            "time": "seconds",
            "distance": "kilometers unless suffixed",
            "sequence_time": "picoseconds",
        },
        "half_link_km": half_link_km,
        "half_link_m": half_link_m,
        "fiber_transmissivity_half_link": fiber_transmissivity_half_link,
        "source_transmissivity": source_transmissivity,
        "arm_transmissivity": arm_transmissivity,
        "detector_signal_probability": p_det_signal,
        "detector_click_probability": p_det,
        "barrett_kok_success_probability": bk_success_probability,
        "barrett_kok_full_success_probability": bk_success_probability,
        "barrett_kok_round2_entry_probability": bk_round2_entry_probability,
        "barrett_kok_round1_time_s": bk_round1_time_s,
        "barrett_kok_round2_time_s": bk_round2_time_s,
        "barrett_kok_effective_attempt_time_s": bk_effective_attempt_time_s,
        "barrett_kok_expected_rate_hz": bk_expected_rate_hz,
        "barrett_kok_raw_fidelity": raw_fidelity,
        "quantum_delay_s": quantum_delay_s,
        "classical_delay_s": classical_delay_s,
        "quantum_delay_ps": quantum_delay_ps,
        "classical_delay_ps": classical_delay_ps,
        "sequence_quantum_attenuation_db_per_m": attenuation_db_per_km / 1000.0,
        "memory_frequency_hz": memory_frequency_hz,
        "barrett_kok_resource_request_arrival_ps": bk_timing["resource_request_arrival_ps"],
        "barrett_kok_protocol_start_primary_ps": bk_timing["protocol_start_primary_ps"],
        "barrett_kok_protocol_start_nonprimary_ps": bk_timing["protocol_start_nonprimary_ps"],
        "barrett_kok_memory_period_ps": bk_timing["memory_period_ps"],
        "barrett_kok_round1_min_emit_ps": bk_timing["round1_min_emit_ps"],
        "barrett_kok_round1_emit_ps": bk_timing["round1_emit_ps"],
        "barrett_kok_round1_failure_time_ps": bk_timing["round1_failure_time_ps"],
        "barrett_kok_round2_min_emit_ps": bk_timing["round2_min_emit_ps"],
        "barrett_kok_round2_emit_ps": bk_timing["round2_emit_ps"],
        "barrett_kok_two_round_time_ps": bk_timing["two_round_time_ps"],
        "barrett_kok_round2_increment_time_ps": bk_timing["round2_increment_time_ps"],
        "barrett_kok_two_round_time_s": bk_two_round_time_s,
        "target_purification_fidelity": target_purification_fidelity,
    }


def require_finite_derived(derived: dict[str, Any]) -> None:
    """Validate that derived floating point values are usable.

    Args:
        derived: Dictionary returned by `derive_parameters`.

    Raises:
        ValueError: If any floating-point derived value is `nan` or infinite.
    """

    for key, value in derived.items():
        if isinstance(value, float) and not isfinite(value):
            raise ValueError(f"derived parameter {key!r} is not finite: {value!r}")
