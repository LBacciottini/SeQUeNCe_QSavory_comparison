module SeQUeNCeQSavoryComparison

using Dates
using ConcurrentSim
using Printf
using QuantumSavory
using QuantumSavory.ProtocolZoo: BBPSSWProt, DistilledTag, EntanglerProt, EntanglementCounterpart, EntanglementTracker, SwapperProt
using QuantumSavory.StatesZoo: BarrettKokBellPair, DepolarizedBellPair
using Random
using Statistics
using TOML

export load_config, resolve_config, derive_parameters, inspect_qsavory_configuration, run_qsavory,
       elementary_rate_theory, run_qsavory_elementary_trials

const PS_PER_SECOND = 1_000_000_000_000

"""Read a shared TOML config file."""
load_config(path::AbstractString) = TOML.parsefile(path)

_require_section(cfg, name) = haskey(cfg, name) || throw(ArgumentError("missing required config section [$name]"))
_prob(name, value) = 0 <= Float64(value) <= 1 || throw(ArgumentError("$name must be in [0, 1], got $value"))
_positive(name, value) = Float64(value) > 0 || throw(ArgumentError("$name must be positive, got $value"))

function _slot_range(name, value, count)
    (value isa Vector && length(value) == 2) || throw(ArgumentError("$name must be a two-element inclusive slot range"))
    lo, hi = Int(value[1]), Int(value[2])
    (0 <= lo <= hi < count) || throw(ArgumentError("$name=$value is outside memory count $count"))
    return lo, hi
end

_overlap(a, b) = max(a[1], b[1]) <= min(a[2], b[2])
_slot_count(a) = a[2] - a[1] + 1

"""
    barrett_kok_fidelity_symmetric(eta, eta_d, visibility, dark_prob)

Return the symmetric Barrett-Kok Bell-state fidelity for the shared model.
"""
function barrett_kok_fidelity_symmetric(eta, eta_d, visibility, dark_prob)
    for (name, value) in (
        ("eta", eta),
        ("eta_d", eta_d),
        ("visibility", visibility),
        ("dark_prob", dark_prob),
    )
        _prob(name, value)
    end
    η = Float64(eta)
    ηd = Float64(eta_d)
    v = Float64(visibility)
    pd = Float64(dark_prob)
    d10 = η * η * ηd * ηd / 4
    d30 = d10 * v * v
    d11 = (1 - pd) * ηd * (2η - 2η * η * ηd) + pd * (1 - η * ηd) * (1 - η * ηd)
    numerator = (1 - pd)^4 * (d10 + d30) + pd * (1 - pd)^2 * d11
    denominator = 2 * (1 - pd)^4 * d10 + 4 * pd * (1 - pd)^2 * d11
    return iszero(denominator) ? NaN : numerator / denominator
end

function _schedule_sequence_transmit_ps(min_time_ps::Integer, frequency_hz::Real)
    time_bin = Float64(min_time_ps) * Float64(frequency_hz) / PS_PER_SECOND
    rounded_bin = ceil(Int, time_bin - 1e-12)
    return Int(rounded_bin * PS_PER_SECOND / Float64(frequency_hz))
end

function _sequence_barrett_kok_timing(;
    quantum_delay_ps::Integer,
    classical_delay_ps::Integer,
    quantum_channel_frequency_hz::Real,
    memory_frequency_hz::Real,
    protocol_gap_ps::Integer,
)
    primary_start_ps = Int(classical_delay_ps)
    nonprimary_start_ps = 2 * Int(classical_delay_ps)
    memory_period_ps = Int(PS_PER_SECOND / Float64(memory_frequency_hz))
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

    return Dict{String,Any}(
        "resource_request_arrival_ps" => primary_start_ps,
        "protocol_start_primary_ps" => primary_start_ps,
        "protocol_start_nonprimary_ps" => nonprimary_start_ps,
        "memory_period_ps" => memory_period_ps,
        "round1_min_emit_ps" => round1_min_emit_ps,
        "round1_emit_ps" => round1_emit_ps,
        "round1_failure_time_ps" => round1_done_ps,
        "round2_min_emit_ps" => round2_min_emit_ps,
        "round2_emit_ps" => round2_emit_ps,
        "two_round_time_ps" => round2_done_ps,
        "round2_increment_time_ps" => round2_done_ps - round1_done_ps,
    )
end

"""Validate fields required by both simulator adapters."""
function validate_config(cfg)
    for section in (
        "experiment", "paths", "topology", "memories", "optics", "detectors",
        "barrett_kok", "resource_reservation", "purification", "swapping", "outputs"
    )
        _require_section(cfg, section)
    end
    _positive("experiment.runtime_s", cfg["experiment"]["runtime_s"])
    _positive("topology.link_length_km", cfg["topology"]["link_length_km"])
    _positive("topology.signal_speed_km_per_s", cfg["topology"]["signal_speed_km_per_s"])
    _positive("optics.quantum_channel_frequency_hz", cfg["optics"]["quantum_channel_frequency_hz"])
    _positive("detectors.count_rate_hz", cfg["detectors"]["count_rate_hz"])
    haskey(cfg["swapping"], "degradation") &&
        throw(ArgumentError("swapping.degradation is not supported; swaps are ideal in this comparison"))
    for (section, key) in (
        ("memories", "emission_efficiency"),
        ("optics", "collection_efficiency"),
        ("optics", "frequency_conversion_efficiency"),
        ("detectors", "efficiency"),
        ("detectors", "dark_count_probability"),
        ("barrett_kok", "mode_matching_visibility"),
        ("swapping", "success_probability"),
    )
        _prob("$section.$key", cfg[section][key])
    end
    cfg["barrett_kok"]["success_probability_model"] == "p_det_squared_over_2" ||
        throw(ArgumentError("only barrett_kok.success_probability_model='p_det_squared_over_2' is supported"))

    counts = Dict(
        "r1" => Int(cfg["memories"]["r1_count"]),
        "r2" => Int(cfg["memories"]["r2_count"]),
        "r3" => Int(cfg["memories"]["r3_count"]),
    )
    flow1 = cfg["resource_reservation"]["flow1"]
    flow2 = cfg["resource_reservation"]["flow2"]
    r1_f1 = _slot_range("flow1.r1_slots", flow1["r1_slots"], counts["r1"])
    r2_f1 = _slot_range("flow1.r2_slots", flow1["r2_slots"], counts["r2"])
    r1_f2 = _slot_range("flow2.r1_slots", flow2["r1_slots"], counts["r1"])
    r2_left = _slot_range("flow2.r2_left_slots", flow2["r2_left_slots"], counts["r2"])
    r2_right = _slot_range("flow2.r2_right_slots", flow2["r2_right_slots"], counts["r2"])
    r3_f2 = _slot_range("flow2.r3_slots", flow2["r3_slots"], counts["r3"])
    !_overlap(r1_f1, r1_f2) || throw(ArgumentError("r1 flow1 and flow2 reservations overlap"))
    (!_overlap(r2_f1, r2_left) && !_overlap(r2_f1, r2_right) && !_overlap(r2_left, r2_right)) ||
        throw(ArgumentError("r2 memory reservations overlap"))
    _slot_count(r1_f1) == _slot_count(r2_f1) ||
        throw(ArgumentError("flow1 r1/r2 reservations must have the same lane count"))
    _slot_count(r1_f2) == _slot_count(r2_left) ||
        throw(ArgumentError("flow2 left-link r1/r2 reservations must have the same lane count"))
    _slot_count(r2_right) == _slot_count(r3_f2) ||
        throw(ArgumentError("flow2 right-link r2/r3 reservations must have the same lane count"))
    return nothing
end

"""Compute simulator-agnostic derived parameters."""
function derive_parameters(cfg)
    link_length_km = Float64(cfg["topology"]["link_length_km"])
    speed_km_per_s = Float64(cfg["topology"]["signal_speed_km_per_s"])
    attenuation_db_per_km = Float64(cfg["optics"]["attenuation_db_per_km"])
    half_link_km = link_length_km / 2
    fiber_transmissivity_half_link = 10.0^(-(attenuation_db_per_km * half_link_km) / 10)
    source_transmissivity = Float64(cfg["memories"]["emission_efficiency"]) *
        Float64(cfg["optics"]["collection_efficiency"]) *
        Float64(cfg["optics"]["frequency_conversion_efficiency"])
    arm_transmissivity = source_transmissivity * fiber_transmissivity_half_link
    detector_efficiency = Float64(cfg["detectors"]["efficiency"])
    dark_prob = Float64(cfg["detectors"]["dark_count_probability"])
    p_det_signal = arm_transmissivity * detector_efficiency
    p_det = p_det_signal + dark_prob - p_det_signal * dark_prob
    bk_success_probability = 0.5 * p_det^2
    bk_round2_entry_probability = sqrt(bk_success_probability)
    quantum_delay_s = half_link_km / speed_km_per_s
    classical_delay_s = link_length_km / speed_km_per_s
    quantum_delay_ps = round(Int, quantum_delay_s * 1e12)
    classical_delay_ps = round(Int, classical_delay_s * 1e12)
    memory_frequency_hz = 1 / max(Float64(cfg["memories"]["excitation_time_s"]), 1e-12)
    protocol_gap_ps = Int(cfg["barrett_kok"]["protocol_gap_ps"])
    bk_timing = _sequence_barrett_kok_timing(
        quantum_delay_ps=quantum_delay_ps,
        classical_delay_ps=classical_delay_ps,
        quantum_channel_frequency_hz=Float64(cfg["optics"]["quantum_channel_frequency_hz"]),
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
        Float64(cfg["barrett_kok"]["mode_matching_visibility"]),
        dark_prob,
    )
    target_fidelity = raw_fidelity^2 + Float64(cfg["purification"]["target_fidelity_margin"])
    return Dict{String,Any}(
        "units" => Dict("time" => "seconds", "sequence_time" => "picoseconds"),
        "half_link_km" => half_link_km,
        "half_link_m" => half_link_km * 1000,
        "fiber_transmissivity_half_link" => fiber_transmissivity_half_link,
        "source_transmissivity" => source_transmissivity,
        "arm_transmissivity" => arm_transmissivity,
        "detector_signal_probability" => p_det_signal,
        "detector_click_probability" => p_det,
        "barrett_kok_success_probability" => bk_success_probability,
        "barrett_kok_full_success_probability" => bk_success_probability,
        "barrett_kok_round2_entry_probability" => bk_round2_entry_probability,
        "barrett_kok_round1_time_s" => bk_round1_time_s,
        "barrett_kok_round2_time_s" => bk_round2_time_s,
        "barrett_kok_effective_attempt_time_s" => bk_effective_attempt_time_s,
        "barrett_kok_expected_rate_hz" => bk_expected_rate_hz,
        "barrett_kok_raw_fidelity" => raw_fidelity,
        "quantum_delay_s" => quantum_delay_s,
        "classical_delay_s" => classical_delay_s,
        "quantum_delay_ps" => quantum_delay_ps,
        "classical_delay_ps" => classical_delay_ps,
        "sequence_quantum_attenuation_db_per_m" => attenuation_db_per_km / 1000,
        "memory_frequency_hz" => memory_frequency_hz,
        "barrett_kok_resource_request_arrival_ps" => bk_timing["resource_request_arrival_ps"],
        "barrett_kok_protocol_start_primary_ps" => bk_timing["protocol_start_primary_ps"],
        "barrett_kok_protocol_start_nonprimary_ps" => bk_timing["protocol_start_nonprimary_ps"],
        "barrett_kok_memory_period_ps" => bk_timing["memory_period_ps"],
        "barrett_kok_round1_min_emit_ps" => bk_timing["round1_min_emit_ps"],
        "barrett_kok_round1_emit_ps" => bk_timing["round1_emit_ps"],
        "barrett_kok_round1_failure_time_ps" => bk_timing["round1_failure_time_ps"],
        "barrett_kok_round2_min_emit_ps" => bk_timing["round2_min_emit_ps"],
        "barrett_kok_round2_emit_ps" => bk_timing["round2_emit_ps"],
        "barrett_kok_two_round_time_ps" => bk_timing["two_round_time_ps"],
        "barrett_kok_round2_increment_time_ps" => bk_timing["round2_increment_time_ps"],
        "barrett_kok_two_round_time_s" => bk_two_round_time_s,
        "target_purification_fidelity" => target_fidelity,
    )
end

"""
    elementary_rate_theory(config)

Return asymptotic Barrett-Kok elementary-link generation-rate expectations.
"""
function elementary_rate_theory(cfg)
    resolved = resolve_config(cfg)
    derived = resolved["derived"]
    return Dict{String,Any}(
        "attempt_success_probability" => Float64(derived["barrett_kok_full_success_probability"]),
        "effective_attempt_time_s" => Float64(derived["barrett_kok_effective_attempt_time_s"]),
        "round2_entry_probability" => Float64(derived["barrett_kok_round2_entry_probability"]),
        "round1_time_s" => Float64(derived["barrett_kok_round1_time_s"]),
        "round2_time_s" => Float64(derived["barrett_kok_round2_time_s"]),
        "expected_rate_hz" => Float64(derived["barrett_kok_expected_rate_hz"]),
        "expected_mean_completion_time_s" => 1 / Float64(derived["barrett_kok_expected_rate_hz"]),
        "expected_raw_fidelity" => Float64(derived["barrett_kok_raw_fidelity"]),
    )
end

function _mean_acceptance_interval(samples; sigma=5.0)
    isempty(samples) && throw(ArgumentError("at least one sample is required"))
    μ = mean(samples)
    if length(samples) == 1
        return μ, μ
    end
    se = std(samples) / sqrt(length(samples))
    return μ - sigma * se, μ + sigma * se
end

"""Return a copied config with a `derived` table."""
function resolve_config(cfg)
    validate_config(cfg)
    resolved = deepcopy(cfg)
    resolved["derived"] = derive_parameters(resolved)
    return resolved
end

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

_json_escape(s::AbstractString) = replace(replace(replace(replace(s, "\\" => "\\\\"), "\"" => "\\\""), "\n" => "\\n"), "\r" => "\\r")

function _json(io, value)
    if value === nothing
        print(io, "null")
    elseif value isa Bool
        print(io, value ? "true" : "false")
    elseif value isa Integer || value isa AbstractFloat
        print(io, value)
    elseif value isa AbstractString
        print(io, '"', _json_escape(value), '"')
    elseif value isa AbstractDict
        print(io, "{")
        first = true
        for key in sort!(collect(keys(value)); by=string)
            first || print(io, ",")
            first = false
            _json(io, string(key)); print(io, ":"); _json(io, value[key])
        end
        print(io, "}")
    elseif value isa AbstractVector || value isa Tuple
        print(io, "[")
        for (i, item) in enumerate(value)
            i == 1 || print(io, ",")
            _json(io, item)
        end
        print(io, "]")
    else
        _json(io, string(value))
    end
end

function write_json(path, value)
    open(path, "w") do io
        _json(io, value)
        println(io)
    end
end

function _write_pairs_csv(path, rows)
    fields = ["simulator", "seed", "flow", "local_node", "local_slot", "remote_node", "remote_slot", "pair_id", "delivery_time_s", "fidelity", "status"]
    open(path, "w") do io
        println(io, join(fields, ","))
        for row in rows
            println(io, join([get(row, field, "") for field in fields], ","))
        end
    end
end

function _write_summary_csv(path, rows)
    fields = ["simulator", "seed", "status", "runtime_s", "completion_time_s", "target_pairs", "target_completed", "flow1_delivered", "flow2_delivered", "flow1_mean_fidelity", "flow2_mean_fidelity"]
    open(path, "w") do io
        println(io, join(fields, ","))
        for row in rows
            println(io, join([get(row, field, "") for field in fields], ","))
        end
    end
end

function _write_elementary_validation_csv(path, rows)
    fields = [
        "simulator", "seed", "trial", "success", "completion_time_s",
        "timeout_s", "effective_attempt_time_s", "success_probability", "round2_entry_probability",
        "round1_time_s", "round2_time_s", "expected_rate_hz",
        "fidelity", "expected_fidelity",
    ]
    open(path, "w") do io
        println(io, join(fields, ","))
        for row in rows
            println(io, join([get(row, field, "") for field in fields], ","))
        end
    end
end

_selector(range_pair) = slot -> Int(range_pair[1]) + 1 <= slot <= Int(range_pair[2]) + 1

function _one_based_slot_pairs(range_a, range_b)
    slots_a = (Int(range_a[1]) + 1):(Int(range_a[2]) + 1)
    slots_b = (Int(range_b[1]) + 1):(Int(range_b[2]) + 1)
    length(slots_a) == length(slots_b) || throw(ArgumentError("paired slot ranges must have the same lane count"))
    return zip(slots_a, slots_b)
end

function _install_lane_entanglers!(sim, net, nodeA, nodeB, rangeA, rangeB, success_prob, attempt_time, pairstate)
    for (slotA, slotB) in _one_based_slot_pairs(rangeA, rangeB)
        @process EntanglerProt(
            sim,
            net,
            nodeA,
            nodeB;
            chooseslotA=slotA,
            chooseslotB=slotB,
            success_prob=success_prob,
            attempt_time=attempt_time,
            pairstate=pairstate,
            retry_lock_time=nothing,
        )()
    end
    return nothing
end

function _normalize_raw_state_model(raw_state_model)
    model = lowercase(String(raw_state_model))
    model in ("exact", "werner") || throw(ArgumentError("raw_state_model must be 'exact' or 'werner', got '$raw_state_model'"))
    return model
end

_qsavory_simulator_label(model) = "qsavory_$(model)"

function _raw_pair_state(resolved, model)
    if model == "exact"
        return BarrettKokBellPair(
            resolved["derived"]["arm_transmissivity"],
            resolved["derived"]["arm_transmissivity"],
            Float64(resolved["detectors"]["dark_count_probability"]),
            Float64(resolved["detectors"]["efficiency"]),
            Float64(resolved["barrett_kok"]["mode_matching_visibility"]),
            Int(resolved["barrett_kok"]["parity_bit"]),
        )
    end
    return DepolarizedBellPair(; F=resolved["derived"]["barrett_kok_raw_fidelity"])
end

function _bell_fidelity(slot_a, slot_b, model, flow="flow1")
    bell = model == "exact" && flow == "flow1" ? (Z₁ ⊗ Z₂ + Z₂ ⊗ Z₁) / sqrt(2) : (Z₁ ⊗ Z₁ + Z₂ ⊗ Z₂) / sqrt(2)
    return real(observable((slot_a, slot_b), SProjector(bell)))
end

function _collect_qsavory_pairs(net, sim, seed, simulator_label, model)
    rows = Vector{Dict{String,Any}}()
    for (remote, flow) in ((2, "flow1"), (3, "flow2"))
        for result in queryall(net[1], EntanglementCounterpart, remote, W, W; locked=false, assigned=true)
            remote_slot = result.tag[3]
            fidelity = try
                _bell_fidelity(result.slot, net[remote][remote_slot], model, flow)
            catch
                ""
            end
            pair_status = !isnothing(query(result.slot, DistilledTag)) ? "PURIFIED" : "ENTANGLED"
            push!(rows, Dict{String,Any}(
                "simulator" => simulator_label,
                "seed" => seed,
                "flow" => flow,
                "local_node" => "r1",
                "local_slot" => result.slot.idx,
                "remote_node" => "r$remote",
                "remote_slot" => remote_slot,
                "pair_id" => string(result.tag[4]),
                "delivery_time_s" => result.time,
                "fidelity" => fidelity,
                "status" => pair_status,
            ))
        end
    end
    return rows
end

function _mean_fidelity(rows)
    values = [row["fidelity"] for row in rows if row["fidelity"] != ""]
    return isempty(values) ? "" : mean(values)
end

function _qsavory_summary_row(simulator_label, seed, runtime_s, pairs, target_pairs, require_purified_flow2=false)
    flow1_rows = [row for row in pairs if row["flow"] == "flow1"]
    observed_flow2_rows = [row for row in pairs if row["flow"] == "flow2"]
    purified_flow2_rows = [row for row in observed_flow2_rows if get(row, "status", "") == "PURIFIED"]
    completion = ""
    if require_purified_flow2
        required_purified = max(target_pairs - 1, 0)
        target_completed = length(observed_flow2_rows) >= target_pairs && length(purified_flow2_rows) >= required_purified
        if target_completed
            flow2_times = sort(Float64[row["delivery_time_s"] for row in observed_flow2_rows])
            purified_times = sort(Float64[row["delivery_time_s"] for row in purified_flow2_rows])
            completion = flow2_times[target_pairs]
            if required_purified > 0
                completion = max(completion, purified_times[required_purified])
            end
        end
    else
        target_completed = length(observed_flow2_rows) >= target_pairs
        if !isempty(observed_flow2_rows)
            times = sort(Float64[row["delivery_time_s"] for row in observed_flow2_rows])
            completion = times[min(target_pairs, length(times))]
        end
    end
    return Dict{String,Any}(
        "simulator" => simulator_label,
        "seed" => seed,
        "status" => "completed",
        "runtime_s" => runtime_s,
        "completion_time_s" => completion,
        "target_pairs" => target_pairs,
        "target_completed" => target_completed,
        "flow1_delivered" => length(flow1_rows),
        "flow2_delivered" => length(observed_flow2_rows),
        "flow1_mean_fidelity" => _mean_fidelity(flow1_rows),
        "flow2_mean_fidelity" => _mean_fidelity(observed_flow2_rows),
    )
end

"""Run independent elementary Barrett-Kok validation trials in QuantumSavory."""
function run_qsavory_elementary_trials(config_path::AbstractString; seed::Integer, trials::Integer, timeout_s::Real, output_dir::Union{Nothing,AbstractString}=nothing, raw_state_model="exact")
    cfg = load_config(config_path)
    resolved = resolve_config(cfg)
    derived = resolved["derived"]
    theory = elementary_rate_theory(cfg)
    model = _normalize_raw_state_model(raw_state_model)
    simulator_label = _qsavory_simulator_label(model)
    rows = Vector{Dict{String,Any}}()
    pairstate = _raw_pair_state(resolved, model)

    for trial in 1:trials
        Random.seed!(seed + trial * 1009)
        net = RegisterNet(
            [Register(1), Register(1)];
            classical_delay=derived["classical_delay_s"],
        )
        sim = get_time_tracker(net)
        @process EntanglerProt(
            sim,
            net,
            1,
            2;
            chooseslotA=1,
            chooseslotB=1,
            rounds=1,
            attempts=-1,
            success_prob=theory["attempt_success_probability"],
            attempt_time=theory["effective_attempt_time_s"],
            pairstate=pairstate,
            retry_lock_time=nothing,
        )()
        run(sim, Float64(timeout_s))

        result = query(net[1], EntanglementCounterpart, 2, W, W; locked=false, assigned=true)
        success = !isnothing(result)
        fidelity = success ? _bell_fidelity(result.slot, net[2][result.tag[3]], model, "flow1") : ""
        push!(rows, Dict{String,Any}(
            "simulator" => simulator_label,
            "seed" => seed,
            "trial" => trial,
            "success" => success,
            "completion_time_s" => success ? result.time : "",
            "timeout_s" => Float64(timeout_s),
            "effective_attempt_time_s" => theory["effective_attempt_time_s"],
            "success_probability" => theory["attempt_success_probability"],
            "round2_entry_probability" => theory["round2_entry_probability"],
            "round1_time_s" => theory["round1_time_s"],
            "round2_time_s" => theory["round2_time_s"],
            "expected_rate_hz" => theory["expected_rate_hz"],
            "fidelity" => fidelity,
            "expected_fidelity" => theory["expected_raw_fidelity"],
        ))
    end

    if !isnothing(output_dir)
        mkpath(output_dir)
        _write_elementary_validation_csv(joinpath(output_dir, "elementary_trials.csv"), rows)
    end
    return rows
end

"""Run the QuantumSavory analytical-BK implementation and write outputs."""
function run_qsavory(config_path::AbstractString, seed::Integer, output_dir::AbstractString; raw_state_model="exact")
    cfg = load_config(config_path)
    resolved = resolve_config(cfg)
    model = _normalize_raw_state_model(raw_state_model)
    simulator_label = _qsavory_simulator_label(model)

    Random.seed!(seed)
    mkpath(output_dir)
    flow1 = resolved["resource_reservation"]["flow1"]
    flow2 = resolved["resource_reservation"]["flow2"]
    derived = resolved["derived"]
    pairstate = _raw_pair_state(resolved, model)
    net = RegisterNet(
        [
            Register(Int(resolved["memories"]["r1_count"])),
            Register(Int(resolved["memories"]["r2_count"])),
            Register(Int(resolved["memories"]["r3_count"])),
        ];
        classical_delay=derived["classical_delay_s"],
    )
    sim = get_time_tracker(net)

    for node in 1:3
        @process EntanglementTracker(sim, net, node)()
    end

    succ = derived["barrett_kok_full_success_probability"]
    attempt_time = derived["barrett_kok_effective_attempt_time_s"]
    _install_lane_entanglers!(sim, net, 1, 2, flow1["r1_slots"], flow1["r2_slots"], succ, attempt_time, pairstate)
    _install_lane_entanglers!(sim, net, 1, 2, flow2["r1_slots"], flow2["r2_left_slots"], succ, attempt_time, pairstate)
    _install_lane_entanglers!(sim, net, 2, 3, flow2["r2_right_slots"], flow2["r3_slots"], succ, attempt_time, pairstate)
    @process BBPSSWProt(sim, net, 1, 3; retry_lock_time=nothing)()
    swap_slots = slot -> Int(flow2["r2_left_slots"][1]) + 1 <= slot <= Int(flow2["r2_right_slots"][2]) + 1
    swap_busy = Float64(resolved["swapping"]["local_busy_time_s"])
    @process SwapperProt(sim, net, 2; nodeL=1, nodeH=3, chooseslots=swap_slots, retry_lock_time=nothing, local_busy_time=swap_busy)()

    run(sim, Float64(resolved["experiment"]["runtime_s"]))
    pairs = _collect_qsavory_pairs(net, sim, seed, simulator_label, model)
    summary = _qsavory_summary_row(
        simulator_label,
        seed,
        Float64(resolved["experiment"]["runtime_s"]),
        pairs,
        Int(flow2["target_pairs"]),
        Bool(resolved["purification"]["enabled"]),
    )
    _write_pairs_csv(joinpath(output_dir, resolved["outputs"]["pairs_filename"]), pairs)
    _write_summary_csv(joinpath(output_dir, resolved["outputs"]["summary_filename"]), [summary])
    manifest = Dict{String,Any}(
        "schema_version" => 1,
        "simulator" => simulator_label,
        "raw_state_model" => model,
        "seed" => seed,
        "created_at" => string(now(UTC)),
        "raw_config" => cfg,
        "resolved_config" => resolved,
        "applied_config" => inspect_qsavory_configuration(cfg; raw_state_model=model),
        "outputs" => resolved["outputs"],
    )
    write_json(joinpath(output_dir, resolved["outputs"]["manifest_filename"]), manifest)
    return Dict("manifest" => manifest, "pairs" => pairs, "summary" => summary)
end

end
