# First Comparison Run

This tutorial runs a one-seed comparison with all three simulator series:
SeQUeNCe, QuantumSavory exact Barrett-Kok, and QuantumSavory Werner.

## 1. Check out the release dependencies

The repository includes vendored simulator snapshots under `dev/`:

```bash
ls dev/SeQUeNCe dev/QuantumSavory.jl
```

You should see both directories.

## 2. Run the Python tests that can import SeQUeNCe

```bash
cd python
PYTHONPATH=src conda run -n sequenceEnv python -m unittest discover -s tests -p 'test_*.py'
cd ..
```

The suite should finish with `OK`. One slow or environment-specific test may be
skipped depending on the active environment.

## 3. Prepare the Julia package

```bash
julia --project=julia/SeQUeNCeQSavoryComparison -e 'using Pkg; Pkg.develop(path="dev/QuantumSavory.jl"); Pkg.instantiate()'
```

This ensures the Julia comparison package uses the vendored QuantumSavory
snapshot.

## 4. Run a one-seed batch

```bash
conda run -n sequenceEnv python scripts/run_batch.py \
  --config shared/configs/default.toml \
  --seeds 1:1 \
  --output outputs/tutorial_batch
```

The output directory should contain one run for each simulator series.

## 5. Generate comparison plots

```bash
conda run -n sequenceEnv python scripts/plot_compare.py \
  --input outputs/tutorial_batch \
  --output outputs/tutorial_batch/comparison.csv
```

The batch directory now contains:

- `comparison.csv`
- `completion_time_by_seed.png`
- `average_fidelity_by_seed.png`

## 6. Inspect one summary

```bash
cat outputs/tutorial_batch/sequence/seed_1/summary.csv
```

The summary row reports completion time, delivered-pair counts, target status,
and mean fidelities for both flows. The same schema is used by all three
simulator series.
