const PS_PER_SECOND = 1_000_000_000_000

"""
    barrett_kok_fidelity_symmetric(eta, eta_d, visibility, dark_prob)

Return the symmetric Barrett-Kok Bell-state fidelity for the shared model.

The formula is the same simulator-agnostic expression used by the Python
adapter.  It assumes symmetric optical arms and combines source/fiber loss
(`eta`), detector efficiency (`eta_d`), mode-matching visibility, and per-round
dark-count probability.

# Arguments

- `eta`: Total transmissivity from each memory to the midpoint beamsplitter.
- `eta_d`: Detector efficiency.
- `visibility`: Two-photon mode-matching visibility.
- `dark_prob`: Dark-count probability per detector window.

# Returns

The conditional raw Bell-pair fidelity.  Returns `NaN` when the detection model
has a zero denominator.

# Examples

```julia
F = barrett_kok_fidelity_symmetric(0.9, 0.95, 0.99, 1e-8)
0 <= F <= 1
```
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

"""
    derive_parameters(cfg) -> Dict{String,Any}

Compute simulator-agnostic derived parameters.

This function is the single source of truth for quantities shared by the
SeQUeNCe and QuantumSavory implementations: half-link loss, arm
transmissivity, Barrett-Kok success probability, SeQUeNCe-equivalent
per-attempt timing, expected elementary-link generation rate, raw fidelity, and
the purification target threshold.

The Barrett-Kok timing mirrors the SeQUeNCe source-level protocol sequence.  A
logical attempt can terminate after round 1 unless the round-1 herald permits
round 2, so the effective attempt time is
`round1_time_s + round2_entry_probability * round2_time_s`.

# Arguments

- `cfg`: Shared configuration dictionary that has passed [`validate_config`](@ref).

# Returns

A dictionary containing derived physical quantities in seconds/meters and
SeQUeNCe timeline quantities in picoseconds.

# Examples

```julia
cfg = load_config("configs/default.toml")
derived = derive_parameters(cfg)
derived["barrett_kok_effective_attempt_time_s"]
```
"""
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
    elementary_rate_theory(cfg) -> Dict{String,Any}

Return asymptotic Barrett-Kok elementary-link generation-rate expectations.

The optional slow validation tests compare many first-success elementary-link
trials against these expectations.  The rate is computed from the shared
effective attempt time and full two-round success probability, not from a fixed
two-round duration.

# Arguments

- `cfg`: Shared configuration dictionary.

# Returns

A dictionary with success probability, effective attempt time, expected rate,
expected mean first-success time, and expected raw fidelity.

# Examples

```julia
theory = elementary_rate_theory(load_config("configs/default.toml"))
theory["expected_mean_completion_time_s"] == 1 / theory["expected_rate_hz"]
```
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
