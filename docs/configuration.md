# Configuration Reference

The canonical shared configuration is `configs/default.toml`. It is the only
place where experiment, hardware, and output parameters should be authored by
hand. Both simulator adapters must read this file through `resolve_config`,
which validates the authored fields and appends a simulator-agnostic `derived`
table.

All times are seconds unless a field name explicitly contains another unit such
as `_ps`. All memory slot ranges are zero-based, inclusive ranges in the shared
configuration. SeQUeNCe consumes those indices directly; QuantumSavory converts
them to one-based register slots inside its adapter.

For simplicity, this comparison deliberately does not model memory decoherence
or memory-lifetime cutoff. Both adapters configure memories/registers with no
storage noise and no expiration policy; the shared config therefore has no
coherence-time or cutoff-ratio entry.

## `[experiment]`

| Key | Type | Unit | Required value or constraint | Meaning |
| --- | --- | --- | --- | --- |
| `name` | string | none | Any descriptive name. | Human-readable experiment label. It is copied into run metadata and should identify the scenario, not the simulator. |
| `runtime_s` | float | seconds | Must be `> 0`. | Maximum simulated time for full experiment runs. SeQUeNCe receives `runtime_s * 1e12` because its timeline is in picoseconds. QuantumSavory receives seconds directly. Elementary slow tests override this value with their per-trial timeout. |
| `seed_start` | integer | none | Intended to be non-negative. | First seed used by multi-seed runners. A runner with `seed_start = 1` and `seed_count = 3` should run seeds `1`, `2`, and `3`. |
| `seed_count` | integer | none | Intended to be `>= 1`. | Number of seeded full experiment repetitions. This controls statistical aggregation; it is not a simulator hardware parameter. |
| `completion_check_interval_s` | float | seconds | Intended to be `> 0`. | Polling cadence for full-run completion checks. It is used by runner logic to decide how often to inspect whether requested end-to-end outputs have been produced. |
| `stop_on_completion` | boolean | none | `true` or `false`. | If enabled, runners may stop a full simulation once requested flow outputs are complete instead of always running until `runtime_s`. |

## `[paths]`

| Key | Type | Unit | Required value or constraint | Meaning |
| --- | --- | --- | --- | --- |
| `sequence_path` | string | filesystem path | Path must resolve to a SeQUeNCe checkout when running SeQUeNCe. | Optional import path prepended by the Python adapter before importing SeQUeNCe. |
| `quantumsavory_path` | string | filesystem path | Path must resolve to the local QuantumSavory checkout when instantiating the Julia project. | Documents the intended local QuantumSavory source tree. The Julia package dependency is pinned through the Julia environment; this field is included in the shared config and manifest so reviewers know which local checkout is expected. |

## `[topology]`

| Key | Type | Unit | Required value or constraint | Meaning |
| --- | --- | --- | --- | --- |
| `node_names` | array of strings | none | Current adapters expect `["r1", "r2", "r3"]`. | Logical repeater-node names. `r1` and `r3` are end nodes; `r2` is the middle repeater. |
| `bsm_names` | array of strings | none | Current adapters expect `["m12", "m23"]`. | Midpoint BSM-node names. `m12` serves links between `r1` and `r2`; `m23` serves links between `r2` and `r3`. |
| `link_length_km` | float | kilometers | Must be `> 0`. | Full elementary-link length between adjacent repeater nodes. The midpoint BSM geometry uses two optical arms of length `link_length_km / 2`. In a three-node chain, both elementary links currently use this same length. |
| `signal_speed_km_per_s` | float | kilometers per second | Must be `> 0`. | Propagation speed used for both quantum and classical delays in the shared model. Derived delays are `quantum_delay_s = (link_length_km / 2) / signal_speed_km_per_s` and `classical_delay_s = link_length_km / signal_speed_km_per_s`. |

## `[memories]`

| Key | Type | Unit | Required value or constraint | Meaning |
| --- | --- | --- | --- | --- |
| `r1_count` | integer | slots | Must be large enough for all `r1` reservations. | Number of memories/register slots at node `r1`. SeQUeNCe creates a `MemoryArray` of this size; QuantumSavory creates a `Register` of this size. |
| `r2_count` | integer | slots | Must be large enough for all `r2` reservations. | Number of memories/register slots at node `r2`. The configured `flow1.r2_slots`, `flow2.r2_left_slots`, and `flow2.r2_right_slots` must be non-overlapping ranges inside this count. |
| `r3_count` | integer | slots | Must be large enough for `flow2.r3_slots`. | Number of memories/register slots at node `r3`. |
| `excitation_time_s` | float | seconds | `0.0` is allowed; the derived model uses `max(excitation_time_s, 1e-12)` to avoid an infinite frequency. | Time between possible memory excitations. The derived memory frequency is `memory_frequency_hz = 1 / max(excitation_time_s, 1e-12)`. SeQUeNCe uses this as `MemoryArray.frequency`; the shared Barrett-Kok timing model uses it to compute `memory_period_ps`. |
| `emission_efficiency` | float | probability | Must be in `[0, 1]`. | Probability that a memory excitation produces an emitted photon before collection and conversion losses. The derived source transmissivity is `emission_efficiency * optics.collection_efficiency * optics.frequency_conversion_efficiency`. |
| `wavelength_nm` | integer or float | nanometers | Informational in the current adapters. | Memory photon wavelength. The current SeQUeNCe and QuantumSavory adapters do not derive loss or state parameters from this value; it is kept in the manifest as hardware metadata. |

## `[optics]`

| Key | Type | Unit | Required value or constraint | Meaning |
| --- | --- | --- | --- | --- |
| `attenuation_db_per_km` | float | dB/km | Intended to be `>= 0`. | Fiber attenuation coefficient. The half-link fiber transmissivity is `10^(-(attenuation_db_per_km * link_length_km / 2) / 10)`. SeQUeNCe receives attenuation as dB/m, so the adapter passes `attenuation_db_per_km / 1000`. |
| `collection_efficiency` | float | probability | Must be in `[0, 1]`. | Probability that an emitted photon is collected into the optical channel before frequency conversion. It is folded into `derived.source_transmissivity`. |
| `frequency_conversion_efficiency` | float | probability | Must be in `[0, 1]`. | Probability that the collected photon survives frequency conversion. It is folded into `derived.source_transmissivity`. |
| `quantum_channel_frequency_hz` | float | hertz | Must be `> 0`. | Quantum-channel clock frequency. SeQUeNCe uses it in `QuantumChannel.schedule_transmit`; the shared derived model mirrors that binning rule when computing Barrett-Kok timing milestones. |

## `[detectors]`

| Key | Type | Unit | Required value or constraint | Meaning |
| --- | --- | --- | --- | --- |
| `efficiency` | float | probability | Must be in `[0, 1]`. | Detector quantum efficiency. It enters the shared click-probability model, the shared raw-fidelity formula, the SeQUeNCe BSM detector template, and the exact QuantumSavory `BarrettKokBellPair` state. |
| `dark_count_probability` | float | probability per modeled detection opportunity | Must be in `[0, 1]`. | Excess detector click probability used by the shared analytical Barrett-Kok success and fidelity formulas and by the exact QuantumSavory `BarrettKokBellPair` state. The Werner QuantumSavory variant receives only the resulting raw fidelity. This field is deliberately separate from SeQUeNCe's detector `dark_count` rate field. |
| `dark_count_rate_hz` | float | hertz | Intended to be `>= 0`. | Rate-like dark-count parameter passed to SeQUeNCe BSM detector templates. It is not used in the shared analytical success-probability formula; that formula uses `dark_count_probability`. |
| `count_rate_hz` | float | hertz | Must be `> 0`. | Maximum BSM detector count rate passed to SeQUeNCe detector templates. |
| `time_resolution_ps` | integer or float | picoseconds | Intended to be `> 0`. | BSM detector time resolution passed to SeQUeNCe detector templates. |

## `[barrett_kok]`

| Key | Type | Unit | Required value or constraint | Meaning |
| --- | --- | --- | --- | --- |
| `mode_matching_visibility` | float | probability-like visibility | Must be in `[0, 1]`. | Interference visibility used in the shared Barrett-Kok raw-fidelity formula and the exact QuantumSavory `BarrettKokBellPair` state. |
| `parity_bit` | integer | none | Current comparisons use `0`. | Click-pattern parity convention passed to the exact QuantumSavory `BarrettKokBellPair`. The SeQUeNCe adapter configures raw fidelity directly, and the Werner QuantumSavory variant uses only the derived raw fidelity. |
| `success_probability_model` | string | none | Must be `"p_det_squared_over_2"`. | Selects the shared elementary success-probability formula. With `eta` as one-arm transmissivity, detector efficiency `eta_d`, and dark probability `p_dark`, the model computes `p_signal = eta * eta_d`, `p_click = p_signal + p_dark - p_signal * p_dark`, and `p_BK = 0.5 * p_click^2`. |
| `protocol_gap_ps` | integer | picoseconds | Current SeQUeNCe source uses `10`; this config should match that value unless the adapter/source model is updated together. | Scheduler gap added by SeQUeNCe after the BSM-result return before the next Barrett-Kok state update. The shared timing model includes this gap in both the first-round failure time and two-round completion time. |

## `[resource_reservation.flow1]`

`flow1` is the direct `r1` to `r2` traffic demand.

| Key | Type | Unit | Required value or constraint | Meaning |
| --- | --- | --- | --- | --- |
| `name` | string | none | Any descriptive flow name. | Human-readable label used in outputs. |
| `source` | string | none | Current adapter expects `"r1"`. | Source node for this flow. |
| `destination` | string | none | Current adapter expects `"r2"`. | Destination node for this flow. |
| `target_pairs` | integer | pairs | Must not exceed the number of reserved `r1_slots`. | Number of requested delivered pairs for completion accounting. |
| `fidelity_min` | float | fidelity | Intended to be in `[0, 1]`. | Requested minimum fidelity. It is recorded as part of the shared flow contract; current elementary validation does not filter pairs by this field. |
| `r1_slots` | two-integer array | memory indices | Inclusive range, `0 <= lo <= hi < memories.r1_count`; must not overlap `flow2.r1_slots`. | Reserved `r1` memory slots for this flow. |
| `r2_slots` | two-integer array | memory indices | Inclusive range, `0 <= lo <= hi < memories.r2_count`; must not overlap either `flow2` range on `r2`. | Reserved `r2` memory slots for this flow. |

## `[resource_reservation.flow2]`

`flow2` is the end-to-end `r1` to `r3` demand that uses both elementary links
and swapping at `r2`.

| Key | Type | Unit | Required value or constraint | Meaning |
| --- | --- | --- | --- | --- |
| `name` | string | none | Any descriptive flow name. | Human-readable label used in outputs. |
| `source` | string | none | Current adapter expects `"r1"`. | Source node for this end-to-end flow. |
| `destination` | string | none | Current adapter expects `"r3"`. | Destination node for this end-to-end flow. |
| `target_pairs` | integer | pairs | Must not exceed the number of reserved `r1_slots`. | Number of requested end-to-end delivered pairs for completion accounting. |
| `fidelity_min` | float | fidelity | Intended to be in `[0, 1]`. | Requested minimum end-to-end fidelity. It is recorded as part of the shared flow contract; current elementary validation does not filter pairs by this field. |
| `r1_slots` | two-integer array | memory indices | Inclusive range, `0 <= lo <= hi < memories.r1_count`; must not overlap `flow1.r1_slots`. | Reserved `r1` slots for the left elementary link of the end-to-end flow. |
| `r2_left_slots` | two-integer array | memory indices | Inclusive range, `0 <= lo <= hi < memories.r2_count`; must not overlap `flow1.r2_slots` or `flow2.r2_right_slots`. | Reserved `r2` slots for the left elementary link, adjacent to `r1`. |
| `r2_right_slots` | two-integer array | memory indices | Inclusive range, `0 <= lo <= hi < memories.r2_count`; must not overlap `flow1.r2_slots` or `flow2.r2_left_slots`. | Reserved `r2` slots for the right elementary link, adjacent to `r3`. Swapping consumes one slot from this range and one from `r2_left_slots`. |
| `r3_slots` | two-integer array | memory indices | Inclusive range, `0 <= lo <= hi < memories.r3_count`. | Reserved `r3` endpoint slots for the right elementary link of the end-to-end flow. |

## `[purification]`

| Key | Type | Unit | Required value or constraint | Meaning |
| --- | --- | --- | --- | --- |
| `enabled` | boolean | none | `true` or `false`. | Enables BBPSSW purification for swapped end-to-end `r1-r3` pairs. Elementary `r1-r2` and `r2-r3` resources are never purified in this scenario. |
| `target_fidelity_policy` | string | none | Current derived model supports `"raw_squared_plus_margin"`. | Policy for deriving the BBPSSW target fidelity from the raw Barrett-Kok fidelity. With the current policy, `target_purification_fidelity = F_raw^2 + target_fidelity_margin`. |
| `target_fidelity_margin` | float | fidelity | Intended to keep the derived target in `[0, 1]`. | Additive margin used by `target_fidelity_policy`. |
| `pair_selection_policy` | string | none | Current adapters document `"first_available"`. | Policy for choosing candidate end-to-end `r1-r3` pairs for purification. It is recorded in applied configuration and should match the implemented BBPSSW selection behavior. |

## `[swapping]`

Swaps are ideal in fidelity throughout this comparison. The shared
configuration controls whether a swap succeeds, but it does not support a
scalar swap-degradation parameter.

| Key | Type | Unit | Required value or constraint | Meaning |
| --- | --- | --- | --- | --- |
| `success_probability` | float | probability | Must be in `[0, 1]`. | Probability that an entanglement-swapping operation succeeds. Passed to SeQUeNCe `EntanglementSwappingA` and QuantumSavory `SwapperProt`. |
| `local_busy_time_s` | float | seconds | Intended to be `>= 0`. | Local operation time for swapping. Passed to QuantumSavory `SwapperProt`; SeQUeNCe support is part of the full-stack mapping surface. |

## `[outputs]`

| Key | Type | Unit | Required value or constraint | Meaning |
| --- | --- | --- | --- | --- |
| `manifest_filename` | string | filename | Should be a relative filename, not an absolute path. | Name of the JSON manifest written in each run directory. The manifest contains raw config, resolved config including `derived`, applied simulator config, seed metadata, and output locations. |
| `pairs_filename` | string | filename | Should be a relative filename, not an absolute path. | Name of the per-pair CSV output. |
| `summary_filename` | string | filename | Should be a relative filename, not an absolute path. | Name of the per-run summary CSV output. |

## Derived Values

The `derived` table is not authored in TOML. It is created by `resolve_config`
and stored in manifests for audit. The most important derived groups are:

- optical geometry: `half_link_km`, `half_link_m`,
  `fiber_transmissivity_half_link`, `source_transmissivity`, and
  `arm_transmissivity`;
- detector/success model: `detector_signal_probability`,
  `detector_click_probability`, `barrett_kok_success_probability`, and
  `barrett_kok_full_success_probability`;
- source-derived Barrett-Kok timing:
  `barrett_kok_round1_failure_time_ps`, `barrett_kok_two_round_time_ps`,
  `barrett_kok_round2_increment_time_ps`,
  `barrett_kok_effective_attempt_time_s`, and
  `barrett_kok_expected_rate_hz`;
- state-quality model: `barrett_kok_raw_fidelity` and
  `target_purification_fidelity`.

See `docs/simulator_mapping.md` for the formal equations and simulator-specific
parameter mapping.
