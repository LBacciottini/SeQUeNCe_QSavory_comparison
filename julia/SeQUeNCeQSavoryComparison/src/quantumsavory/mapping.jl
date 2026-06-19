"""Return the exact QuantumSavory settings implied by the shared config."""
function inspect_qsavory_configuration(cfg; raw_state_model="exact")
    resolved = resolve_config(cfg)
    flow1 = resolved["resource_reservation"]["flow1"]
    flow2 = resolved["resource_reservation"]["flow2"]
    model = _normalize_raw_state_model(raw_state_model)
    flow1_lanes = Int(flow1["r1_slots"][2]) - Int(flow1["r1_slots"][1]) + 1
    flow2_left_lanes = Int(flow2["r1_slots"][2]) - Int(flow2["r1_slots"][1]) + 1
    flow2_right_lanes = Int(flow2["r2_right_slots"][2]) - Int(flow2["r2_right_slots"][1]) + 1
    return Dict{String,Any}(
        "register_counts" => Dict(
            "r1" => Int(resolved["memories"]["r1_count"]),
            "r2" => Int(resolved["memories"]["r2_count"]),
            "r3" => Int(resolved["memories"]["r3_count"]),
        ),
        "memory_noise" => Dict("background" => "none"),
        "raw_state" => Dict(
            "model" => model,
            "simulator_label" => _qsavory_simulator_label(model),
            "class" => model == "exact" ? "BarrettKokBellPair" : "DepolarizedBellPair",
            "fidelity_observables" => Dict(
                "flow1" => model == "exact" ? "psi_plus_01" : "phi_plus_00_11",
                "flow2" => "phi_plus_00_11",
            ),
            "raw_fidelity" => resolved["derived"]["barrett_kok_raw_fidelity"],
            "werner_depolarization_parameter" => (4 * resolved["derived"]["barrett_kok_raw_fidelity"] - 1) / 3,
        ),
        "slot_ranges" => Dict(
            "flow1_r1_slots" => flow1["r1_slots"],
            "flow1_r2_slots" => flow1["r2_slots"],
            "flow2_r1_slots" => flow2["r1_slots"],
            "flow2_r2_left_slots" => flow2["r2_left_slots"],
            "flow2_r2_right_slots" => flow2["r2_right_slots"],
            "flow2_r3_slots" => flow2["r3_slots"],
        ),
        "barrett_kok_state" => Dict(
            "etaA" => resolved["derived"]["arm_transmissivity"],
            "etaB" => resolved["derived"]["arm_transmissivity"],
            "dark_count_probability" => Float64(resolved["detectors"]["dark_count_probability"]),
            "detector_efficiency" => Float64(resolved["detectors"]["efficiency"]),
            "mode_matching_visibility" => Float64(resolved["barrett_kok"]["mode_matching_visibility"]),
            "parity_bit" => Int(resolved["barrett_kok"]["parity_bit"]),
        ),
        "entangler" => Dict(
            "multiplexing" => "one_entangler_per_reserved_memory_lane",
            "lane_counts" => Dict(
                "flow1_r1_r2" => flow1_lanes,
                "flow2_r1_r2_left" => flow2_left_lanes,
                "flow2_r2_right_r3" => flow2_right_lanes,
                "total" => flow1_lanes + flow2_left_lanes + flow2_right_lanes,
            ),
            "success_probability" => resolved["derived"]["barrett_kok_full_success_probability"],
            "effective_attempt_time_s" => resolved["derived"]["barrett_kok_effective_attempt_time_s"],
            "round2_entry_probability" => resolved["derived"]["barrett_kok_round2_entry_probability"],
            "round1_time_s" => resolved["derived"]["barrett_kok_round1_time_s"],
            "round2_time_s" => resolved["derived"]["barrett_kok_round2_time_s"],
            "two_round_time_s" => resolved["derived"]["barrett_kok_two_round_time_s"],
            "resource_request_arrival_ps" => resolved["derived"]["barrett_kok_resource_request_arrival_ps"],
            "protocol_start_primary_ps" => resolved["derived"]["barrett_kok_protocol_start_primary_ps"],
            "protocol_start_nonprimary_ps" => resolved["derived"]["barrett_kok_protocol_start_nonprimary_ps"],
            "memory_period_ps" => resolved["derived"]["barrett_kok_memory_period_ps"],
            "round1_min_emit_ps" => resolved["derived"]["barrett_kok_round1_min_emit_ps"],
            "round1_emit_ps" => resolved["derived"]["barrett_kok_round1_emit_ps"],
            "round1_failure_time_ps" => resolved["derived"]["barrett_kok_round1_failure_time_ps"],
            "round2_min_emit_ps" => resolved["derived"]["barrett_kok_round2_min_emit_ps"],
            "round2_emit_ps" => resolved["derived"]["barrett_kok_round2_emit_ps"],
            "two_round_time_ps" => resolved["derived"]["barrett_kok_two_round_time_ps"],
            "round2_increment_time_ps" => resolved["derived"]["barrett_kok_round2_increment_time_ps"],
        ),
        "distillation" => Dict(
            "scope" => "end_to_end_only",
            "nodeA" => "r1",
            "nodeB" => "r3",
            "target_fidelity" => resolved["derived"]["target_purification_fidelity"],
            "pair_selection_policy" => resolved["purification"]["pair_selection_policy"],
        ),
        "swapping" => Dict(
            "success_probability" => Float64(resolved["swapping"]["success_probability"]),
            "fidelity_model" => "ideal",
            "local_busy_time_s" => Float64(resolved["swapping"]["local_busy_time_s"]),
            "retry_lock_time" => nothing,
            "retry_policy" => "event_based",
        ),
    )
end
