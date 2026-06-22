# Outputs

Each simulator run writes three artifacts into its output directory.
Batch runs use three simulator labels: `sequence`, `qsavory_exact`, and
`qsavory_werner`.

Batch and sweep runners also write `jobs.csv` in the batch root. It records one
row per launched simulator process, plus a `julia_prewarm` pseudo-job when
parallel QuantumSavory runs require precompilation before workers start.

## `manifest.json`

The manifest is language-agnostic JSON with:

- `schema_version`
- `simulator`
- `raw_state_model` for QuantumSavory runs
- `seed`
- `created_at`
- `raw_config`
- `resolved_config`
- `applied_config`
- `outputs`

Tests compare `applied_config` against `resolved_config` to catch adapter drift.
For QuantumSavory, `applied_config.raw_state` records the selected raw-state
model, state class, per-flow fidelity observables, and raw fidelity.

## `pairs.csv`

One row per delivered or observed pair:

- simulator
- seed
- flow
- local node and slot
- remote node and slot
- pair id
- delivery time
- fidelity
- status: for flow2, distinguishes raw swapped `ENTANGLED` pairs from
  BBPSSW-distilled `PURIFIED` pairs when the simulator exposes that state.

## `summary.csv`

One row per run:

- simulator
- seed
- status
- runtime
- completion time: the first time at which the configured end-to-end flow2
  inventory condition is satisfied. With BBPSSW enabled, the default target of
  `10` flow2 pairs is considered reached when there are `9` purified
  end-to-end pairs and one additional raw swapped end-to-end pair. If the
  target is not reached, this field is empty.
- delivered counts per flow. Flow2 counts all observed end-to-end `r1-r3`
  pairs, including raw swapped `ENTANGLED` pairs and BBPSSW-distilled
  `PURIFIED` pairs.
- target pair count and whether the target was reached
- mean fidelity per flow, computed over all counted pairs for that flow

## `elementary_trials.csv`

Optional elementary-link validation helpers may write this file when called
with an output directory. Each row is one first-success Barrett-Kok validation
trial:

- simulator, seed, and trial index
- success flag and completion time
- configured attempt time and attempt success probability
- expected rate and raw fidelity from shared theory
- observed raw-pair fidelity for successful trials

## `jobs.csv`

`jobs.csv` is written by `scripts/run_batch.py` and `scripts/run_sweep.py`.
One simulator job is one seed in one simulator variant; sweep jobs also include
one link length. The file records:

- `job_id`, `kind`, `simulator`, `seed`, and optional `link_length_km`;
- generated config path and output directory;
- status: `succeeded`, `failed`, `terminated`, or `cancelled`;
- return code, timestamps, elapsed wall-clock seconds, and command.

The runners use fail-fast semantics. After the first nonzero job exit, no new
jobs are launched, running jobs are terminated, pending jobs are marked
`cancelled`, and the runner exits nonzero.

## Comparison Plots

`scripts/plot_compare.py` reads all nested `summary.csv` files under a batch
directory. In the default `--mode batch`, it writes:

- `comparison.csv`: aggregate completion-time statistics by simulator, with
  separate counts for runs that have a timing value and runs that reached the
  configured target pair count;
- `completion_time_by_seed.png`: completion time versus seed;
- `average_fidelity_by_seed.png`: average fidelity versus seed.

The average-fidelity plot uses `flow2_mean_fidelity` by default, because flow2
is the end-to-end repeater-chain output. Pass `--fidelity-field
flow1_mean_fidelity` to plot elementary-link fidelity instead.

## Link-Length Sweep Outputs

`scripts/run_sweep.py` runs the seeded batch workflow for multiple
`topology.link_length_km` values. The default sweep is `5,10,20,30,40` km.
Each length is stored as a normal batch subdirectory:

```text
outputs/link_length_sweep/
  sweep_manifest.json
  link_005km/
    config.toml
    sequence/seed_1/{manifest.json,pairs.csv,summary.csv}
    qsavory_werner/seed_1/{manifest.json,pairs.csv,summary.csv}
    qsavory_exact/seed_1/{manifest.json,pairs.csv,summary.csv}
```

`sweep_manifest.json` records the sweep parameter, link lengths, seeds,
requested simulators, base config path, worker count, Julia prewarm status,
timestamp, and layout version. Each `link_XXXkm/config.toml` is the generated
shared config passed to both simulators for that length.

Use sweep plot mode to aggregate over seeds and put link length on the x-axis:

```bash
python3 scripts/plot_compare.py --mode sweep --input outputs/link_length_sweep --output outputs/link_length_sweep/sweep_comparison.csv
```

This writes:

- `sweep_comparison.csv`: aggregate statistics by link length and simulator,
  including means, standard deviations, and 95% confidence intervals;
- `completion_time_by_link_length.png`: mean completion time versus elementary
  link length with 95% confidence intervals;
- `average_fidelity_by_link_length.png`: mean flow2 fidelity versus elementary
  link length with 95% confidence intervals.
