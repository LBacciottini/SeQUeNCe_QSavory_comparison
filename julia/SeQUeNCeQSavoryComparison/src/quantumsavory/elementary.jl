"""
    run_qsavory_elementary_trials(config_path; seed, trials, timeout_s,
                                  output_dir=nothing, raw_state_model="exact")

Run independent elementary Barrett-Kok validation trials in QuantumSavory.

Each trial creates a fresh two-node `RegisterNet` with one memory per node and
one `EntanglerProt`.  The entangler uses the shared Barrett-Kok full-success
probability and SeQUeNCe-equivalent effective attempt time, so the slow
validation layer checks that QuantumSavory's elementary-link abstraction has
the same asymptotic first-success rate and raw fidelity as the shared theory.

# Arguments

- `config_path`: Path to the shared TOML configuration.
- `seed`: Base random seed.  Each trial receives a deterministic offset.
- `trials`: Number of independent first-success experiments.
- `timeout_s`: Maximum simulated time per trial, in seconds.
- `output_dir`: Optional directory where `elementary_trials.csv` is written.
- `raw_state_model`: `"exact"` for `BarrettKokBellPair` or `"werner"` for
  `DepolarizedBellPair`.

# Returns

A vector of row dictionaries with observed success, completion time, fidelity,
and theoretical rate/fidelity columns.

# Examples

```julia
rows = run_qsavory_elementary_trials(
    "configs/default.toml";
    seed=1,
    trials=10,
    timeout_s=1.0,
    raw_state_model="exact",
)
rows[1]["simulator"]
```
"""
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
