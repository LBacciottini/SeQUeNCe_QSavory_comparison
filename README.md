# SeQUeNCe / QuantumSavory Cross Validation

This repository compares the same quantum-network experiment in two simulators:
SeQUeNCe in Python and QuantumSavory in Julia. Both simulators read the same
shared hardware configuration, translate it into simulator-specific objects, and
write the same output schema for seeded statistical comparison.

The experiment implemented here is the
[SeQUeNCe resource-management tutorial](https://sequence-rtd-tutorial.readthedocs.io/stable/tutorial/chapter4/resource_management.html):
a three-router repeater chain with a short `r1-r2` flow and a long `r1-r3`
flow using elementary generation, swapping, and purification. QuantumSavory is
run in two raw-state variants: an exact Barrett-Kok state model and a
Werner/depolarized state model with the same raw fidelity.

## LLM Disclosure

The core QuantumSavory and SeQUeNCe simulations were implemented manually. The
intellectual design of the physics-specific shared configuration, including the
choice of physical parameters and the mapping from shared parameters into
simulator-specific configurations, was also developed manually.

Codex 0.141.0 was used to wire the shared configuration into reusable adapters,
wrap the experiment runners, organize seeded batch and sweep execution, collect
simulation outputs, generate comparison plots, write and expand source
docstrings, and assemble the documentation pages.

## Repository Contents

- `shared/configs/default.toml`: canonical simulator-agnostic hardware and
  experiment configuration.
- `shared/testdata/`: simulator-agnostic reference cases used by both language
  test suites.
- `python/src/sequence_qsavory_comparison/common`: shared Python utilities for
  configuration parsing, derived formulas, output schemas, plotting, manifests,
  and validation helpers.
- `python/src/sequence_qsavory_comparison/sequence`: SeQUeNCe adapter and
  simulation setup.
- `julia/SeQUeNCeQSavoryComparison/src`: Julia package with the QuantumSavory
  mapping, simulation setup, and result writing.
- `scripts/`: root command-line entry points for simulator runs, batches,
  sweeps, diagnostics, plotting, and docs generation.
- `dev/SeQUeNCe` and `dev/QuantumSavory.jl`: vendored simulator snapshots used
  by this public repository.
- `python/tests/` and `julia/SeQUeNCeQSavoryComparison/test/`: Python and Julia
  test suites.
- `docs/`: Diátaxis documentation source: tutorials, how-to guides, reference,
  explanation, and generated API pages.

## Installation

Clone the repository and enter the project root:

```bash
git clone https://github.com/LBacciottini/SeQUeNCe_QSavory_comparison.git
cd SeQUeNCe_QSavory_comparison
```

The SeQUeNCe commands assume that you have a conda environment named
`sequenceEnv` where SeQUeNCe and its Python dependencies are installed. This
repository vendors the SeQUeNCe source under `dev/SeQUeNCe`; install or expose
that checkout inside `sequenceEnv` according to your local SeQUeNCe workflow.

The Python comparison package is used from source:

```bash
conda activate sequenceEnv
export PYTHONPATH="$PWD/python/src"
```

Prepare the Julia comparison package and make sure it uses the vendored
QuantumSavory snapshot:

```bash
julia --project=julia/SeQUeNCeQSavoryComparison -e 'using Pkg; Pkg.develop(path="dev/QuantumSavory.jl"); Pkg.instantiate()'
```

## Quick Start

Run the Python tests that can import SeQUeNCe:

```bash
cd python
PYTHONPATH=src conda run -n sequenceEnv python -m unittest discover -s tests -p 'test_*.py'
cd ..
```

Run the Julia package tests:

```bash
julia --project=julia/SeQUeNCeQSavoryComparison -e 'using Pkg; Pkg.test()'
```

Run a one-seed comparison with all three simulator series:

```bash
conda run -n sequenceEnv python scripts/run_batch.py \
  --config shared/configs/default.toml \
  --seeds 1:1 \
  --output outputs/tutorial_batch
```

Generate comparison plots for that batch:

```bash
conda run -n sequenceEnv python scripts/plot_compare.py \
  --input outputs/tutorial_batch \
  --output outputs/tutorial_batch/comparison.csv
```

The batch directory will contain `comparison.csv`,
`completion_time_by_seed.pdf`, and `average_fidelity_by_seed.pdf`.

## Batches And Sweeps

Run SeQUeNCe and both QuantumSavory variants across a seed range:

```bash
conda run -n sequenceEnv python scripts/run_batch.py \
  --config shared/configs/default.toml \
  --seeds 1:30 \
  --output outputs/batch \
  --parallel
```

One job is one seed in one simulator variant. Use `--parallel` for an automatic
worker count or `--workers N` for an explicit count.

Run a link-length sweep with seeded repetitions:

```bash
conda run -n sequenceEnv python scripts/run_sweep.py \
  --config shared/configs/default.toml \
  --link-lengths 5:50:5 \
  --seeds 1:30 \
  --output outputs/link_length_sweep \
  --parallel
```

Generate sweep plots with link length on the x-axis:

```bash
conda run -n sequenceEnv python scripts/plot_compare.py \
  --mode sweep \
  --input outputs/link_length_sweep \
  --output outputs/link_length_sweep/sweep_comparison.csv
```

This writes `sweep_comparison.csv`,
`completion_time_by_link_length.pdf`, and
`average_fidelity_by_link_length.pdf`.

## Documentation

The documentation is organized with the [Diátaxis](https://diataxis.fr)
structure:

- **Tutorials** teach the workflow through a small guided run.
- **How-to guides** give task-focused commands for running experiments,
  plotting results, validating agreement, and building documentation.
- **Reference** describes the configuration, output schema, simulator mapping,
  tests, vendored simulator snapshots, and generated APIs.
- **Explanation** discusses why the comparison is structured this way and how to
  interpret the modeling choices.

Start with `docs/tutorials/first-comparison.md` if you are new to the project.
For the experiment contract and simulator mappings, read
`docs/reference/configuration.md`, `docs/reference/parameter-mapping.md`, and
`docs/explanation/cross-validation-model.md`.

Build the documentation site:

```bash
python3 -m pip install -r docs/requirements.txt
PYTHONPATH=python/src python3 scripts/build_docs.py
```

Serve it locally:

```bash
PYTHONPATH=python/src python3 -m mkdocs serve
```

Generated outputs and built documentation artifacts are ignored by git.
