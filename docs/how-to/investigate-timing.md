# Investigate Timing Discrepancies

Use the diagnostic campaign when aggregate completion times disagree and the
elementary-link validation alone is not enough to identify the first divergent
layer.

## Run a smoke campaign

```bash
PYTHONPATH=python/src python scripts/run_diagnostic_campaign.py \
  --config shared/configs/default.toml \
  --seeds 1:3 \
  --scenarios smoke \
  --output outputs/diagnostics/smoke \
  --parallel
```

The smoke campaign runs:

- `single_lane_elementary`
- `same_link_multilane`
- `eg_swap_no_purification`
- `full_reduced`

For SeQUeNCe, run the command from an environment that can import SeQUeNCe, for
example the `sequenceEnv` conda environment used by the simulator runner.

## Run targeted attribution scenarios

```bash
PYTHONPATH=python/src python scripts/run_diagnostic_campaign.py \
  --config shared/configs/default.toml \
  --seeds 1:30 \
  --scenarios single_lane_elementary,same_link_multilane,competing_flows_same_bsm,two_link_no_swap,eg_swap_no_purification,full_reduced \
  --output outputs/diagnostics/attribution \
  --parallel
```

The scenarios isolate layers in this order:

- `single_lane_elementary`: one Barrett-Kok lane, no swapping or purification.
- `same_link_multilane`: multiple memory lanes on one elementary link.
- `competing_flows_same_bsm`: flow1 and flow2-left share `m12`.
- `two_link_no_swap`: both elementary links run without swap consumption.
- `eg_swap_no_purification`: elementary generation plus ideal swapping.
- `full_reduced`: reduced full scenario with purification enabled.

## Inspect outputs

Each diagnostic run writes:

- `events.csv`: timestamped simulator events.
- `stage_summary.csv`: aggregate counts and timing by stage and event.
- `diagnostic_manifest.json`: scenario, seed, config, and derived parameters.

SeQUeNCe diagnostics include resource-manager and Barrett-Kok handshake events.
QuantumSavory diagnostics currently record delivered-pair events with the same
schema, which is enough to compare the stage at which observable throughput
first diverges. When the first divergent scenario is found, add narrower event
hooks only for that layer.

The root-cause rule is to compare scenarios in order and fix the first layer
where simulator confidence intervals no longer overlap. Then keep the reduced
scenario as an optional regression test.

## Generate the root-cause report

```bash
PYTHONPATH=python/src python scripts/analyze_diagnostics.py \
  --input outputs/diagnostics/attribution \
  --output outputs/diagnostics/attribution_report \
  --reference sequence \
  --candidate qsavory_exact
```

The analyzer writes:

- `diagnostic_comparison.csv`: scenario-by-stage timing means, confidence
  intervals, and relative gaps.
- `root_cause_report.md`: the first divergent layer in scenario order and the
  corresponding fix interpretation.

Fix only the first divergent layer. For example, if
`competing_flows_same_bsm / elementary_delivered` is the first mismatch, adjust
shared-link contention before changing swapping or purification behavior.
