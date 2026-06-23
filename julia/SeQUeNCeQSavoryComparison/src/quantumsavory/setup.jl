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

"""
    run_qsavory(config_path, seed, output_dir; raw_state_model="exact") -> Dict

Run the QuantumSavory analytical-Barrett-Kok implementation and write outputs.

The runner builds a three-register `RegisterNet`, starts one `EntanglerProt`
per reserved memory lane, runs `SwapperProt` at the middle node, and runs
`BBPSSWProt` only between the end nodes `r1` and `r3`.  The distiller enables
QuantumSavory's initial classical handshake so its BBPSSW reservation timing
matches SeQUeNCe.  The elementary entanglers use the shared effective
Barrett-Kok attempt time and full-success probability derived from the same
configuration used by the SeQUeNCe adapter.

Two raw-state models are supported:

- `"exact"` uses `BarrettKokBellPair` with the derived optical parameters.
- `"werner"` uses `DepolarizedBellPair` with the same raw fidelity, giving a
  Werner-state abstraction that can be compared directly to SeQUeNCe's BDS
  representation.

# Arguments

- `config_path`: Path to the shared TOML configuration.
- `seed`: Random seed for QuantumSavory and Julia's global RNG.
- `output_dir`: Directory where `pairs.csv`, `summary.csv`, and
  `manifest.json` are written.
- `raw_state_model`: `"exact"` or `"werner"`.

# Returns

A dictionary containing the in-memory `manifest`, `pairs`, and `summary`
objects that were also written to disk.

# Examples

```julia
result = run_qsavory(
    "configs/default.toml",
    7,
    "results/qsavory_exact/seed_7";
    raw_state_model="exact",
)
result["summary"]["simulator"] == "qsavory_exact"
```
"""
function run_qsavory(config_path::AbstractString, seed::Integer, output_dir::AbstractString; raw_state_model="exact")
    cfg = load_config(config_path)
    resolved = resolve_config(cfg)
    return _run_qsavory_resolved(cfg, resolved, seed, output_dir; raw_state_model)
end

function _run_qsavory_resolved(cfg, resolved, seed::Integer, output_dir::AbstractString; raw_state_model="exact", diagnostic_scenario=nothing)
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
    scenario = isnothing(diagnostic_scenario) ? "production" : String(diagnostic_scenario)
    install_flow1 = isnothing(diagnostic_scenario) || scenario in ("single_lane_elementary", "same_link_multilane", "competing_flows_same_bsm", "full_reduced")
    install_flow2_left = isnothing(diagnostic_scenario) || scenario in ("competing_flows_same_bsm", "two_link_no_swap", "eg_swap_no_purification", "full_reduced")
    install_flow2_right = isnothing(diagnostic_scenario) || scenario in ("two_link_no_swap", "eg_swap_no_purification", "full_reduced")
    install_swap = isnothing(diagnostic_scenario) || scenario in ("eg_swap_no_purification", "full_reduced")
    install_purification = isnothing(diagnostic_scenario) || (scenario == "full_reduced" && Bool(resolved["purification"]["enabled"]))

    install_flow1 && _install_lane_entanglers!(sim, net, 1, 2, flow1["r1_slots"], flow1["r2_slots"], succ, attempt_time, pairstate)
    install_flow2_left && _install_lane_entanglers!(sim, net, 1, 2, flow2["r1_slots"], flow2["r2_left_slots"], succ, attempt_time, pairstate)
    install_flow2_right && _install_lane_entanglers!(sim, net, 2, 3, flow2["r2_right_slots"], flow2["r3_slots"], succ, attempt_time, pairstate)
    install_purification && @process BBPSSWProt(sim, net, 1, 3; retry_lock_time=nothing, initial_handshake=true)()
    if install_swap
        swap_slots = slot -> Int(flow2["r2_left_slots"][1]) + 1 <= slot <= Int(flow2["r2_right_slots"][2]) + 1
        swap_busy = Float64(resolved["swapping"]["local_busy_time_s"])
        @process SwapperProt(sim, net, 2; nodeL=1, nodeH=3, chooseslots=swap_slots, retry_lock_time=nothing, local_busy_time=swap_busy)()
    end

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
    return Dict("manifest" => manifest, "pairs" => pairs, "summary" => summary, "net" => net, "sim" => sim)
end
