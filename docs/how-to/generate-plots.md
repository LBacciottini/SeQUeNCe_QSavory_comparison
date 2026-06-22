# Generate Plots

## Plot a seeded batch

```bash
conda run -n sequenceEnv python scripts/plot_compare.py \
  --input outputs/batch \
  --output outputs/batch/comparison.csv
```

This writes:

- `comparison.csv`
- `completion_time_by_seed.pdf`
- `average_fidelity_by_seed.pdf`

The fidelity plot uses `flow2_mean_fidelity` by default. To plot elementary
flow fidelity instead:

```bash
conda run -n sequenceEnv python scripts/plot_compare.py \
  --input outputs/batch \
  --output outputs/batch/comparison_flow1.csv \
  --fidelity-field flow1_mean_fidelity
```

## Plot a link-length sweep

```bash
conda run -n sequenceEnv python scripts/plot_compare.py \
  --mode sweep \
  --input outputs/link_length_sweep \
  --output outputs/link_length_sweep/sweep_comparison.csv
```

This writes:

- `sweep_comparison.csv`
- `completion_time_by_link_length.pdf`
- `average_fidelity_by_link_length.pdf`
