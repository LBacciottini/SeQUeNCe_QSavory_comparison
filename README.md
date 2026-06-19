# SeQUeNCe / QuantumSavory Cross Validation

This repository implements a cross-validation experiment between SeQUeNCe
(Python) and QuantumSavory (Julia). Both simulators consume the same hardware
configuration, adapt it into simulator-specific objects, and write a shared
output schema for comparison. QuantumSavory is run in two raw-state variants:
an exact Barrett-Kok state and a Werner/depolarized state with the same raw
fidelity.

The first target experiment is the SeQUeNCe resource-management tutorial:
a three-node repeater chain with a short `r1-r2` flow and a long `r1-r3`
flow using elementary Barrett-Kok generation, BBPSSW purification, and swapping
at `r2`.

## Layout

- `shared/configs/default.toml` is the canonical shared configuration.
- `shared/testdata/` contains simulator-agnostic reference cases used by both
  language test suites.
- `python/src/sequence_qsavory_comparison/common` contains Python config
  parsing, derived formulas, plotting, validation, and manifest helpers.
- `python/src/sequence_qsavory_comparison/sequence` adapts the shared config
  to SeQUeNCe.
- `julia/SeQUeNCeQSavoryComparison/src` contains the Julia package, including
  the QuantumSavory mapping and simulation setup.
- `scripts/` contains CLI entry points for single-simulator and batch runs.
- `python/tests/` contains Python config/formula/schema tests and SeQUeNCe
  adapter tests.
- `julia/SeQUeNCeQSavoryComparison/test/` contains Julia package tests,
  following Julia's `Pkg.test()` convention.
- `docs/` explains the config, simulator mapping, outputs, and test strategy.

## Quick Start

Run Python tests that do not require simulator dependencies:

```bash
cd python
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
```

Run the full Python test suite, including the SeQUeNCe smoke integration test:

```bash
cd python
PYTHONPATH=src conda run -n sequenceEnv python -m unittest discover -s tests -p 'test_*.py'
```

Run a SeQUeNCe simulation when SeQUeNCe is available, for example from the
`sequenceEnv` conda environment:

```bash
conda run -n sequenceEnv python scripts/run_sequence.py --config shared/configs/default.toml --seed 1 --output outputs/sequence_seed1
```

Run a QuantumSavory simulation after developing the local QuantumSavory checkout
into the Julia environment:

```bash
julia --project=julia/SeQUeNCeQSavoryComparison -e 'using Pkg; Pkg.develop(path=".agents/codebases/QuantumSavory.jl"); Pkg.instantiate()'
julia --project=julia/SeQUeNCeQSavoryComparison scripts/run_qsavory.jl --config shared/configs/default.toml --seed 1 --raw-state-model exact --output outputs/qsavory_exact_seed1
julia --project=julia/SeQUeNCeQSavoryComparison scripts/run_qsavory.jl --config shared/configs/default.toml --seed 1 --raw-state-model werner --output outputs/qsavory_werner_seed1
```

Run SeQUeNCe and both QuantumSavory variants across a seed range:

```bash
python3 scripts/run_batch.py --config shared/configs/default.toml --seeds 1:10 --output outputs/batch
```

Run optional elementary-link statistical validation tests:

```bash
RUN_SLOW_SIM_TESTS=1 conda run -n sequenceEnv python -m unittest tests.test_sequence_elementary_slow
RUN_SLOW_SIM_TESTS=1 julia --project=julia/SeQUeNCeQSavoryComparison -e 'using Pkg; Pkg.test()'
```

Generated outputs are ignored by git.
