# Simulator Mapping Reference

This page is the reference for how the shared configuration in
`shared/configs/default.toml` is translated into SeQUeNCe and QuantumSavory objects.
All simulator parameters must come from either the authored TOML fields or the
derived values produced by `resolve_config`.

Related references:

- `reference/configuration.md` describes the shared config sections.
- `manifest.json` records `raw_config`, `resolved_config`, and
  `applied_config` for each run.
- `reference/testing-strategy.md` lists the tests that compare applied simulator settings and
  elementary-link behavior against this mapping.

## Shared Derived Model

Let the authored link length be `L = topology.link_length_km`, the signal speed
be `v = topology.signal_speed_km_per_s`, and the attenuation coefficient be
`alpha = optics.attenuation_db_per_km`.

The midpoint BSM geometry uses a half-link optical arm:

```text
L_half_km = L / 2
L_half_m  = 1000 * L_half_km
```

The fiber transmissivity of one arm is:

```text
T_fiber = 10 ^ (-(alpha * L_half_km) / 10)
```

The end-to-midpoint optical arm transmissivity used by the Barrett-Kok model is:

```text
eta_source = memories.emission_efficiency
           * optics.collection_efficiency
           * optics.frequency_conversion_efficiency
eta = eta_source * T_fiber
```

The derived value `barrett_kok_success_probability` is computed only from
shared configuration fields in `[memories]`, `[optics]`, `[detectors]`, and
`[barrett_kok]`. First, with detector efficiency
`eta_d = detectors.efficiency` and excess detector click probability
`p_dark = detectors.dark_count_probability`, the probability that one detector
arm clicks is:

```text
p_signal = eta * eta_d
p_click  = p_signal + p_dark - p_signal * p_dark
```

The configured Barrett-Kok success probability model is
`barrett_kok.success_probability_model = "p_det_squared_over_2"`, hence:

```text
p_BK = 0.5 * p_click^2
```

This value is stored as:

```text
derived.barrett_kok_success_probability = p_BK
derived.barrett_kok_full_success_probability = p_BK
```

The current success-probability model is deliberately simple: it treats
Barrett-Kok success as one half times the square of the single-arm click
probability. The single-arm click probability includes signal clicks and dark
clicks while avoiding double-counting the event where both occur in the same
arm.

Timing values are:

```text
quantum_delay_s    = L_half_km / v
classical_delay_s  = L / v
quantum_delay_ps   = round(quantum_delay_s * 1e12)
classical_delay_ps = round(classical_delay_s * 1e12)
```

SeQUeNCe models Barrett-Kok as two optical rounds. The second round is reached
only if the first round produced a valid BSM result. QuantumSavory keeps using
`EntanglerProt`, which samples a geometric number of fixed-duration Bernoulli
attempts. Therefore the shared model maps the explicit SeQUeNCe short-circuit
process into the expected duration of one logical Barrett-Kok attempt.

The effective first-round pass probability is:

```text
p_round2 = sqrt(p_BK)
```

This preserves the full logical success probability:

```text
p_BK = p_round2^2
```

The round duration is computed by replaying the SeQUeNCe scheduling path in
closed form. This is not a guessed latency budget. It mirrors the source path
used by `ResourceManager.send_request`, `ResourceManager.received_message`,
`EntanglementGenerationA.start`, `EntanglementGenerationA.received_message`,
and `QuantumChannel.schedule_transmit`.

The current SeQUeNCe adapter gives all classical channels the same full-link
delay, including endpoint-to-midpoint BSM-result channels:

```text
memory_frequency_hz = 1 / max(memories.excitation_time_s, 1e-12)
memory_period_ps = floor(1e12 / memory_frequency_hz)
C = classical_delay_ps
Q = quantum_delay_ps
gap = barrett_kok.protocol_gap_ps
```

For one logical attempt starting when the requesting resource-manager rule
fires at time `t = 0`:

```text
resource_request_arrival_ps = C
protocol_start_primary_ps = C
protocol_start_nonprimary_ps = 2C

round1_min_emit_ps = max(2C, 0) + C
round1_emit_ps = schedule_transmit(round1_min_emit_ps)
round1_failure_time_ps = round1_emit_ps + Q + C + gap

next_excite_ps = round1_emit_ps + memory_period_ps
round2_min_emit_ps = max(round1_failure_time_ps + C, next_excite_ps) + C
round2_emit_ps = schedule_transmit(round2_min_emit_ps)
two_round_time_ps = round2_emit_ps + Q + C + gap
round2_increment_time_ps = two_round_time_ps - round1_failure_time_ps
```

Here `schedule_transmit` is SeQUeNCe's quantum-channel clock rule:

```text
time_bin = ceil(min_time_ps * optics.quantum_channel_frequency_hz / 1e12)
scheduled_time_ps = floor(time_bin * 1e12 / optics.quantum_channel_frequency_hz)
```

The first optical round includes resource-manager pairing, Barrett-Kok
negotiate/ack scheduling, photon flight to the midpoint, the BSM-result return,
and the protocol gap. The second optical round starts from the already-paired
protocols, so it omits the initial resource-manager request/response but still
has Barrett-Kok negotiation, photon flight, BSM-result return, protocol gap,
memory excitation cadence, and quantum-channel bin rounding.

The compressed times used by QuantumSavory are:

```text
round1_time_s = round1_failure_time_ps * 1e-12
round2_time_s = round2_increment_time_ps * 1e-12
two_round_time_s = two_round_time_ps * 1e-12
```

The expected compressed attempt time passed to QuantumSavory is:

```text
effective_attempt_time_s = round1_time_s + p_round2 * round2_time_s
expected_rate_hz = p_BK / effective_attempt_time_s
```

These values are stored as:

```text
derived.barrett_kok_round2_entry_probability = p_round2
derived.barrett_kok_round1_time_s = round1_time_s
derived.barrett_kok_round2_time_s = round2_time_s
derived.barrett_kok_two_round_time_s = two_round_time_s
derived.barrett_kok_effective_attempt_time_s = effective_attempt_time_s
derived.barrett_kok_expected_rate_hz = expected_rate_hz
```

The `resolved_config.derived` table also stores the intermediate picosecond
milestones listed above, so the manifest can be audited against the scheduling
equations. The `1e-12` lower bound on authored zero excitation time prevents an
infinite memory frequency.

The shared Barrett-Kok raw fidelity uses the symmetric `etaA = etaB = eta`
formula. Let `V = barrett_kok.mode_matching_visibility`:

```text
d10 = eta^2 * eta_d^2 / 4
d30 = d10 * V^2
d11 = (1 - p_dark) * eta_d * (2 * eta - 2 * eta^2 * eta_d)
    + p_dark * (1 - eta * eta_d)^2

F_raw = ((1 - p_dark)^4 * (d10 + d30) + p_dark * (1 - p_dark)^2 * d11)
      / (2 * (1 - p_dark)^4 * d10 + 4 * p_dark * (1 - p_dark)^2 * d11)
```

The current purification threshold policy is:

```text
F_target = F_raw^2 + purification.target_fidelity_margin
```

These values appear in `resolved_config.derived` and are the formal source for
both adapters.

## SeQUeNCe Mapping

SeQUeNCe is used as a lower-level event-driven model with explicit quantum
routers, BSM nodes, optical channels, detector templates, resource-manager
rules, and protocol instances. The adapter code is in
`python/src/sequence_qsavory_comparison/sequence`.

| Shared value | SeQUeNCe target | Mapping and rationale |
| --- | --- | --- |
| `experiment.runtime_s` | `Timeline(runtime_s * 1e12)` | SeQUeNCe timelines are configured in picoseconds. |
| `memories.r*_count` | `QuantumRouter(..., memo_size=count)` | Each router owns a SeQUeNCe `MemoryArray`; counts are copied exactly. |
| `derived.barrett_kok_raw_fidelity` | `MemoryArray.raw_fidelity` | SeQUeNCe's Barrett-Kok protocol writes successful elementary pairs with the memory's raw fidelity. |
| `derived.memory_frequency_hz` | `MemoryArray.frequency` | This controls memory excitation cadence. |
| `derived.source_transmissivity` | `MemoryArray.efficiency` | SeQUeNCe has one pre-channel photon-emission loss parameter here, so emission, collection, and frequency-conversion efficiencies are folded together before fiber loss. |
| no authored memory-decoherence field | `MemoryArray.coherence_time = -1`, `decoherence_rate = 0`, `cutoff_flag = false` | Memory decoherence and memory-lifetime cutoff are intentionally disabled for this comparison. |
| `detectors.efficiency` | BSM detector template `efficiency` | Copied directly to the two `SingleAtomBSM` detectors. |
| `detectors.dark_count_rate_hz` | BSM detector template `dark_count` | SeQUeNCe expects a rate-like detector parameter here, so the config keeps it separate from analytical `dark_count_probability`. |
| `detectors.count_rate_hz` | BSM detector template `count_rate` | Copied directly. |
| `detectors.time_resolution_ps` | BSM detector template `time_resolution` | Copied directly in picoseconds. |
| `derived.half_link_m` | `QuantumChannel.distance` | Each router-to-midpoint arm is half of the full link. |
| `derived.sequence_quantum_attenuation_db_per_m` | `QuantumChannel.attenuation` | SeQUeNCe expects attenuation per meter, so `dB/km` is divided by `1000`. |
| `derived.quantum_delay_ps` | `QuantumChannel.delay` via distance/light-speed model | The applied config reports the derived expected delay for audit. |
| `derived.classical_delay_ps` | `ClassicalChannel(delay=...)` | Classical channels are explicit all-to-all control paths in picoseconds. |
| `optics.quantum_channel_frequency_hz` | `QuantumChannel.frequency` | Copied directly. |

Resource reservations remain zero-based because SeQUeNCe memory indices are
zero-based. The resource-manager rule conditions use inclusive configured slot
ranges, for example `[10, 19]` means memory indices `10` through `19`.

Protocol mapping:

| Shared behavior | SeQUeNCe implementation |
| --- | --- |
| `flow1` elementary `r1-r2` pairs | Entanglement-generation rules on `r1` and `r2` through midpoint `m12`. |
| `flow2` left elementary link | Entanglement-generation rules on `r1` and `r2` through `m12`, using `flow2.r1_slots` and `flow2.r2_left_slots`. |
| `flow2` right elementary link | Entanglement-generation rules on `r2` and `r3` through `m23`, using `flow2.r2_right_slots` and `flow2.r3_slots`. |
| BBPSSW purification | `BBPSSWProtocol` rules select two same-remote, same-fidelity swapped `r1-r3` memories below `F_target`. No elementary-link memory is eligible for purification. |
| Swapping at `r2` | `EntanglementSwappingA` consumes one valid left-link and one valid right-link memory at `r2`; endpoint nodes install `EntanglementSwappingB`. |
| Swap success | `swapping.success_probability` is passed to `EntanglementSwappingA`. |
| Swap fidelity model | Ideal. The adapter resets SeQUeNCe's circuit-swap `degradation` attribute to `1.0` when that attribute exists, because the comparison does not support non-ideal swap noise. |

The SeQUeNCe applied mapping is machine-checkable with
`inspect_sequence_configuration`, which is stored in `manifest.json` as
`applied_config`.

## QuantumSavory Mapping

QuantumSavory is used as a higher-level analytical/state-based model. The
adapter constructs registers, analytical raw-pair states, asynchronous
ProtocolZoo processes, and tag-based endpoint metadata. The adapter code is in
`julia/SeQUeNCeQSavoryComparison/src/quantumsavory`, with shared Julia config,
physics, I/O, and summary helpers in `julia/SeQUeNCeQSavoryComparison/src`.
Each QuantumSavory experiment is run in two raw-state variants:

- `qsavory_exact`, using the full analytical `BarrettKokBellPair`;
- `qsavory_werner`, using `DepolarizedBellPair` with the same raw fidelity.

| Shared value | QuantumSavory target | Mapping and rationale |
| --- | --- | --- |
| `memories.r*_count` | `Register(count)` | Each network node is a QuantumSavory register with one slot per memory. |
| no authored memory-decoherence field | plain `Register(count)` without a background process | Memory decoherence and memory-lifetime cutoff are intentionally disabled for this comparison. |
| `derived.classical_delay_s` | `RegisterNet(...; classical_delay=...)` | QuantumSavory uses seconds for simulation time. |
| `derived.arm_transmissivity` | `BarrettKokBellPair(etaA, etaB, ...)` in `qsavory_exact` | The current geometry is symmetric, so `etaA = etaB = eta`. |
| `detectors.dark_count_probability` | `BarrettKokBellPair(..., Pd, ...)` in `qsavory_exact` | QuantumSavory's Barrett-Kok state uses detector excess noise probability. |
| `detectors.efficiency` | `BarrettKokBellPair(..., eta_d, ...)` in `qsavory_exact` | Copied directly into the analytical state. |
| `barrett_kok.mode_matching_visibility` | `BarrettKokBellPair(..., V, ...)` in `qsavory_exact` | Copied directly. |
| `barrett_kok.parity_bit` | `BarrettKokBellPair(..., m)` in `qsavory_exact` | Selects the click-pattern parity convention. |
| `derived.barrett_kok_raw_fidelity` | `DepolarizedBellPair(; F=...)` in `qsavory_werner` | The Werner/depolarized approximation preserves only the same raw Bell-state fidelity as the exact Barrett-Kok model. |
| `derived.barrett_kok_full_success_probability` | one `EntanglerProt(success_prob=...)` per reserved memory lane | Entanglement success is sampled as a geometric number of compressed logical attempts. The adapter starts fixed-slot entanglers for each paired memory lane so the reserved memory array is multiplexed, matching SeQUeNCe's memory-level rule behavior. |
| `derived.barrett_kok_effective_attempt_time_s` | per-lane `EntanglerProt(attempt_time=...)` | One sampled attempt advances simulation time by the expected SeQUeNCe short-circuit duration. |
| resource reservation ranges | fixed `chooseslotA` and `chooseslotB` integers for entanglers; range predicates for swapping | Shared config ranges are zero-based; QuantumSavory slots are one-based, so each lane adds one exactly once. Paired elementary-link ranges must have equal lane counts. |
| swap fidelity model | `SwapperProt` without additional noise | QuantumSavory swaps are ideal in this comparison. The shared config has no scalar swap-degradation field. |
| swap retry timing | `SwapperProt(retry_lock_time=nothing)` | Swapping is event-based: when no swappable pair exists, the protocol waits for a tag change instead of polling on a fixed interval. |
| `swapping.local_busy_time_s` | `SwapperProt(local_busy_time=...)` | Copied directly. |

QuantumSavory slot ranges are the one place where the adapter changes indexing
convention. A shared range `[lo, hi]` becomes the predicate:

```text
lo + 1 <= slot <= hi + 1
```

Protocol mapping:

| Shared behavior | QuantumSavory implementation |
| --- | --- |
| Elementary links | Three `EntanglerProt` processes: `r1-r2` for `flow1`, `r1-r2` for `flow2` left, and `r2-r3` for `flow2` right. The processes use the compressed short-circuit attempt duration from the shared derived model. |
| Endpoint metadata | `EntanglementCounterpart` tags store remote node, remote slot, and pair id. |
| Metadata updates after swapping | `EntanglementTracker` runs on all three nodes so tag updates and deletions propagate. |
| BBPSSW purification | `BBPSSWProt(sim, net, 1, 3)` operates only over candidate endpoint `r1-r3` pairs using ProtocolZoo tag queries. |
| Swapping at `r2` | `SwapperProt(sim, net, 2; nodeL=1, nodeH=3, chooseslots=...)` consumes middle-node memories in the reserved left/right ranges. |

The exact Barrett-Kok analytical state is a single-excitation Bell state. For
parity bit `m = 0`, the raw flow1 fidelity observable used by `qsavory_exact`
is:

```text
|psi_BK> = (|01> + |10>) / sqrt(2)
F = <psi_BK| rho |psi_BK>
```

In QuantumSavory symbolic notation this is evaluated for raw elementary pairs
as:

```text
SProjector((Z1 tensor Z2 + Z2 tensor Z1) / sqrt(2))
```

For flow2, the reported QuantumSavory fidelity is the end-to-end state after
entanglement swapping at `r2`. The default swapper convention maps two
single-excitation elementary Bell pairs to the endpoint `|phi+>` Bell target,
so `qsavory_exact` and `qsavory_werner` both report flow2 fidelity against:

```text
|phi+> = (|00> + |11>) / sqrt(2)
F = <phi+| rho |phi+>
```

The Werner/depolarized approximation uses QuantumSavory's
`DepolarizedBellPair(; F=derived.barrett_kok_raw_fidelity)`, which is centered
on the same `|phi+>` target:

```text
|phi+> = (|00> + |11>) / sqrt(2)
F = <phi+| rho |phi+>
```

The two QuantumSavory variants therefore have the same configured raw fidelity
and generation-rate parameters, but different raw density matrices. Their
flow1 observables differ because `BarrettKokBellPair` represents the physical
single-excitation Barrett-Kok state while `DepolarizedBellPair` represents a
Werner approximation centered on `|phi+>`. Their flow2 observable is the same
endpoint Bell target after swapping.

The QuantumSavory applied mapping is machine-checkable with
`inspect_qsavory_configuration`, which is stored in `manifest.json` as
`applied_config`.

## Semantic Differences and Validation Status

The two simulators do not implement identical internal mechanisms.

SeQUeNCe explicitly models memory excitation, photon transmission through
quantum channels, BSM detector events, classical messages, resource-manager
rules, and protocol state transitions. Successful Barrett-Kok generation writes
the configured raw fidelity onto the memory.

QuantumSavory models Barrett-Kok generation analytically: `EntanglerProt`
samples a geometric number of attempts from `success_prob`, waits
`attempts * attempt_time`, and initializes the selected slots with
the selected raw-state model. Its `attempt_time` is not a literal two-round
optical trace; it is the expected SeQUeNCe short-circuit duration
`round1_time_s + p_round2 * round2_time_s`.

This is intentional. The comparison validates that both simulators implement
the same experiment-level model, not that their internal event mechanisms are
identical.

Current validation status:

- Config and formula tests validate the shared derived values.
- Adapter inspection tests validate that applied simulator settings match the
  shared config and derived values.
- Optional elementary-link tests validate that both simulators match the shared
  Barrett-Kok generation rate and raw fidelity in isolation, using the
  short-circuit effective attempt duration.
- Full repeater-chain effects such as BBPSSW behavior, swapping behavior,
  memory contention, and final end-to-end metrics require separate validation
  layers.

## Mapping Checklist

Use this checklist when changing a mapping:

- Every simulator parameter is traceable to `raw_config` or
  `resolved_config.derived`.
- Every unit conversion is explicit, especially seconds versus picoseconds and
  kilometers versus meters.
- Every index conversion is explicit; SeQUeNCe uses zero-based memory indices,
  while QuantumSavory register slots are one-based.
- Every intentional modeling difference is named in this document.
- `manifest.json.applied_config` contains enough information to audit the
  realized simulator settings after a run.
- Tests in `reference/testing-strategy.md` cover the mapping category being changed.
