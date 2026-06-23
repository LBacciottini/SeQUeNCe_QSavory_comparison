"""
    SeQUeNCeQSavoryComparison

Cross-validation utilities for comparing the [SeQUeNCe resource-management
  tutorial scenario](https://sequence-rtd-tutorial.readthedocs.io/stable/tutorial/chapter4/resource_management.html) with an analogous QuantumSavory implementation.

The package reads the shared TOML configuration, derives simulator-independent
Barrett-Kok timing and fidelity quantities, runs the QuantumSavory simulator
variants, and writes the same manifest/CSV schema used by the Python SeQUeNCe
adapter.
"""
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
       elementary_rate_theory, run_qsavory_elementary_trials, run_qsavory_diagnostic

include("config.jl")
include("physics.jl")
include("io.jl")
include("summary.jl")
include("quantumsavory/states.jl")
include("quantumsavory/mapping.jl")
include("quantumsavory/elementary.jl")
include("quantumsavory/setup.jl")
include("diagnostics.jl")

end
