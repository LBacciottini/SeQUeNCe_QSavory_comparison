# Run a Diagnostic Campaign

This tutorial runs a small diagnostic campaign and turns it into a root-cause
report. It is meant for the first time you need to explain why two simulator
curves differ before changing model code.

The same campaign also serves as sub-step validation. Before trusting full
completion-time or fidelity curves, use diagnostics to check that SeQUeNCe and
QuantumSavory agree at each configured layer: elementary generation,
multiplexing, shared-resource contention, swapping, purification, and final
completion accounting.

## 1. Activate the SeQUeNCe environment

Run the commands from the repository root. The SeQUeNCe side expects a conda
environment named `sequenceEnv` with SeQUeNCe and its dependencies installed.

```bash
conda activate sequenceEnv
export PYTHONPATH=python/src
```

## 2. Run the smoke scenarios

The smoke campaign exercises one elementary lane, multilane generation on one
link, generation plus swapping, and the reduced full model with purification.

```bash
python scripts/run_diagnostic_campaign.py \
  --config shared/configs/default.toml \
  --seeds 1:3 \
  --scenarios smoke \
  --output outputs/tutorial_diagnostics/smoke \
  --parallel
```

Each run writes an `events.csv`, a compact `stage_summary.csv`, and a
`diagnostic_manifest.json`.

## 3. Compare SeQUeNCe to QuantumSavory Werner

Use the analyzer on the compact stage summaries:

```bash
python scripts/analyze_diagnostics.py \
  --input outputs/tutorial_diagnostics/smoke \
  --output outputs/tutorial_diagnostics/smoke_report \
  --reference sequence \
  --candidate qsavory_werner
```

The report directory contains:

- `diagnostic_comparison.csv`
- `root_cause_report.md`

Open the root-cause report:

```bash
cat outputs/tutorial_diagnostics/smoke_report/root_cause_report.md
```

If no first divergence is reported, widen the campaign before changing code.

## 4. Run the attribution scenarios

The full attribution set isolates one layer at a time:

```bash
python scripts/run_diagnostic_campaign.py \
  --config shared/configs/default.toml \
  --seeds 1:10 \
  --scenarios all \
  --output outputs/tutorial_diagnostics/attribution \
  --parallel
```

Then analyze the result:

```bash
python scripts/analyze_diagnostics.py \
  --input outputs/tutorial_diagnostics/attribution \
  --output outputs/tutorial_diagnostics/attribution_report \
  --reference sequence \
  --candidate qsavory_werner
```

Inspect `diagnostic_comparison.csv` when the root-cause report points at a
stage. The columns `relative_gap`, `ci95_overlaps`, and
`event_counts_match` are the first checks to read.

## 5. Interpret the first divergent layer

Read scenarios in model order, not in the order that looks largest:

1. `single_lane_elementary`
2. `same_link_multilane`
3. `competing_flows_same_bsm`
4. `two_link_no_swap`
5. `eg_swap_no_purification`
6. `full_reduced`

Fix the earliest layer whose confidence intervals no longer overlap, then keep
that reduced scenario as a regression test.

When all reduced layers agree, the full comparison has stronger evidence than a
single end-to-end plot: each simulator has been checked against the other at
every sub-step that composes the experiment.

For example, if elementary scenarios agree but `full_reduced` differs, the
problem is downstream of elementary generation and swapping. In the current
comparison, a BBPSSW success-probability check showed that SeQUeNCe's stock
circuit purifier did not match the intended Werner model, so the adapter uses
the `comparison_werner_bbpssw` purification protocol documented in
[Parameter Mapping](../reference/parameter-mapping.md).
