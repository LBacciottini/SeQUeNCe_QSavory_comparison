# Outputs

Each simulator run writes three artifacts into its output directory.
Batch runs use three simulator labels: `sequence`, `qsavory_exact`, and
`qsavory_werner`.

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

## Comparison Plots

`scripts/plot_compare.py` reads all nested `summary.csv` files under a batch
directory and writes:

- `comparison.csv`: aggregate completion-time statistics by simulator, with
  separate counts for runs that have a timing value and runs that reached the
  configured target pair count;
- `completion_time_by_seed.png`: completion time versus seed;
- `average_fidelity_by_seed.png`: average fidelity versus seed.

The average-fidelity plot uses `flow2_mean_fidelity` by default, because flow2
is the end-to-end repeater-chain output. Pass `--fidelity-field
flow1_mean_fidelity` to plot elementary-link fidelity instead.
