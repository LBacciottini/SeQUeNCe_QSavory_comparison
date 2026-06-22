# Simulator Semantics

SeQUeNCe and QuantumSavory do not simulate the repeater chain with identical
internal machinery.

SeQUeNCe explicitly represents resource-manager rules, memory objects,
Barrett-Kok protocol messages, optical-channel timing, BSM results, and memory
state updates. Its event trace is close to the protocol mechanics.

QuantumSavory uses higher-level protocol objects and analytical state models.
For elementary generation, the adapter keeps `EntanglerProt` and compresses the
source-derived SeQUeNCe short-circuit behavior into an expected attempt
duration:

```text
effective_attempt_time_s = round1_time_s + p_round2 * round2_time_s
```

That compression is intentional. The validation target is not an identical
event trace; it is the same experiment-level rate, fidelity, reservation, swap,
and purification behavior.

The exact timing equations and parameter tables are in
[Parameter Mapping](../reference/parameter-mapping.md).
