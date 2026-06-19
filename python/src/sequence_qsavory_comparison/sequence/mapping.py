"""Map the shared config into explicit SeQUeNCe adapter settings."""

from __future__ import annotations

from typing import Any

from sequence_qsavory_comparison.common.config import resolve_config


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
