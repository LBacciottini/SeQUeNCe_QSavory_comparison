module SeQUeNCeQSavoryComparison

using ConcurrentSim
using Dates
using Printf
using QuantumSavory
using QuantumSavory.ProtocolZoo: BBPSSWProt, DistilledTag, EntanglerProt, EntanglementCounterpart, EntanglementTracker, SwapperProt
using QuantumSavory.StatesZoo: BarrettKokBellPair, DepolarizedBellPair
using Random
using Statistics
using TOML

export load_config, resolve_config, derive_parameters, inspect_qsavory_configuration, run_qsavory,
       elementary_rate_theory, run_qsavory_elementary_trials

include("config.jl")
include("physics.jl")
include("io.jl")
include("summary.jl")
include("quantumsavory/states.jl")
include("quantumsavory/mapping.jl")
include("quantumsavory/elementary.jl")
include("quantumsavory/setup.jl")

end
