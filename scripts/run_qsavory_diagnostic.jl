#!/usr/bin/env julia
using SeQUeNCeQSavoryComparison

function _print_help()
    println("""
    usage: run_qsavory_diagnostic.jl [--config CONFIG] --seed SEED --scenario SCENARIO --output OUTPUT [--raw-state-model MODEL]

    optional arguments:
      -h, --help                 show this help message and exit
      --config CONFIG            shared TOML config path, default shared/configs/default.toml
      --seed SEED                integer random seed
      --scenario SCENARIO        diagnostic scenario name
      --output OUTPUT            output directory
      --raw-state-model MODEL    exact or werner, default exact
    """)
end

function _argvalue(args, name, default=nothing)
    idx = findfirst(==(name), args)
    isnothing(idx) && return default
    idx == length(args) && error("missing value after $name")
    return args[idx + 1]
end

if "-h" in ARGS || "--help" in ARGS
    _print_help()
    exit(0)
end

config = _argvalue(ARGS, "--config", "shared/configs/default.toml")
seed_arg = _argvalue(ARGS, "--seed")
scenario = _argvalue(ARGS, "--scenario")
output = _argvalue(ARGS, "--output")
isnothing(seed_arg) && error("missing required --seed")
isnothing(scenario) && error("missing required --scenario")
isnothing(output) && error("missing required --output")
seed = parse(Int, seed_arg)
raw_state_model = _argvalue(ARGS, "--raw-state-model", "exact")
run_qsavory_diagnostic(config, seed, output; scenario, raw_state_model)
