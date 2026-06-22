# Run Batches and Sweeps

## Run a seeded batch

```bash
conda run -n sequenceEnv python scripts/run_batch.py \
  --config shared/configs/default.toml \
  --seeds 1:30 \
  --output outputs/batch \
  --workers 4
```

The batch runner creates three simulator series by default:

- `sequence`
- `qsavory_exact`
- `qsavory_werner`

One job is one seed in one simulator variant. Use `--parallel` for an automatic
worker count or `--workers N` for an explicit count.

## Run a link-length sweep

```bash
conda run -n sequenceEnv python scripts/run_sweep.py \
  --config shared/configs/default.toml \
  --link-lengths 5,10,20,30,40 \
  --seeds 1:30 \
  --output outputs/link_length_sweep \
  --workers 4
```

The sweep runner writes one generated shared config per link length and records
the run layout in `sweep_manifest.json`.

## Avoid Julia precompile contention

Parallel QuantumSavory runs execute one blocking Julia prewarm job before
starting worker processes. Keep the default prewarm behavior unless the Julia
environment is already warm and stable.
