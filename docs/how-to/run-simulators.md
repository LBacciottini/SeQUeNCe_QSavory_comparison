# Run Simulators

The SeQUeNCe commands assume you have created a conda environment named
`sequenceEnv` and installed SeQUeNCe together with its Python dependencies in
that environment. The QuantumSavory commands use the Julia project in this
repository and the vendored `dev/QuantumSavory.jl` checkout.

## Run SeQUeNCe

```bash
conda run -n sequenceEnv python scripts/run_sequence.py \
  --config shared/configs/default.toml \
  --seed 1 \
  --output outputs/sequence_seed1
```

## Run QuantumSavory with the exact raw state

```bash
julia --project=julia/SeQUeNCeQSavoryComparison scripts/run_qsavory.jl \
  --config shared/configs/default.toml \
  --seed 1 \
  --raw-state-model exact \
  --output outputs/qsavory_exact_seed1
```

## Run QuantumSavory with the Werner raw-state model

```bash
julia --project=julia/SeQUeNCeQSavoryComparison scripts/run_qsavory.jl \
  --config shared/configs/default.toml \
  --seed 1 \
  --raw-state-model werner \
  --output outputs/qsavory_werner_seed1
```

QuantumSavory must be developed from the vendored source at
`dev/QuantumSavory.jl`:

```bash
julia --project=julia/SeQUeNCeQSavoryComparison -e 'using Pkg; Pkg.develop(path="dev/QuantumSavory.jl"); Pkg.instantiate()'
```
