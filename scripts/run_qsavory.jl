#!/usr/bin/env julia
using SeQUeNCeQSavoryComparison

function _argvalue(args, name, default=nothing)
    idx = findfirst(==(name), args)
    isnothing(idx) && return default
    idx == length(args) && error("missing value after $name")
    return args[idx + 1]
end

config = _argvalue(ARGS, "--config", "configs/default.toml")
seed = parse(Int, _argvalue(ARGS, "--seed"))
output = _argvalue(ARGS, "--output")
raw_state_model = _argvalue(ARGS, "--raw-state-model", "exact")
run_qsavory(config, seed, output; raw_state_model)
