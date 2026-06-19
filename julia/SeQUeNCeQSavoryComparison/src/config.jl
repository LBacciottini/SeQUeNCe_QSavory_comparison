"""Read a shared TOML config file."""
load_config(path::AbstractString) = TOML.parsefile(_resolve_input_path(path))

function _resolve_input_path(path::AbstractString)
    isabspath(path) && return path
    isfile(path) && return path
    dir = abspath(pwd())
    while true
        candidate = joinpath(dir, path)
        isfile(candidate) && return candidate
        parent = dirname(dir)
        parent == dir && break
        dir = parent
    end
    return path
end

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

"""Return a copied config with a `derived` table."""
function resolve_config(cfg)
    validate_config(cfg)
    resolved = deepcopy(cfg)
    resolved["derived"] = derive_parameters(resolved)
    return resolved
end
