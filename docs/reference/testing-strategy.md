# Testing Strategy

The tests are designed to fail when a simulator silently applies a different
configuration than the shared TOML file specifies.

## Test Layout

The repository keeps each language's tests inside that language's package
boundary:

- `python/tests/` is the Python test suite. From `python/`, it is discovered
  with `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'`
  when the package is not installed editable.
- `julia/SeQUeNCeQSavoryComparison/test/` is the Julia package test suite.
  Julia's package manager expects `test/runtests.jl` relative to the active
  package project, so it is run with
  `julia --project=julia/SeQUeNCeQSavoryComparison -e 'using Pkg; Pkg.test()'`.

## Common Tests

- TOML schema validation.
- Probability and positive-value bounds.
- Memory-range overlap detection.
- Barrett-Kok formulas and derived timing values.

## Adapter Inspection Tests

Each simulator exposes an inspection function that returns all applied settings:
register/memory counts, slot ranges, channel delays, detector parameters,
Barrett-Kok state/timing, purification settings, and swap settings.

Inspection tests should be the first line of defense because they catch
configuration mismatches before stochastic simulations are involved.

The SeQUeNCe adapter also has a real smoke integration test. It is skipped in a
plain Python environment and runs when `sequenceEnv` can import SeQUeNCe and its
dependencies:

```bash
cd python
PYTHONPATH=src conda run -n sequenceEnv python -m unittest discover -s tests -p 'test_*.py'
```

## Component Tests

Component tests should cover:

- Barrett-Kok link-length, detector-efficiency, dark-count, and visibility dependence.
- Barrett-Kok short-circuit timing:
  source-derived SeQUeNCe resource-manager handshakes, Barrett-Kok negotiation,
  quantum-channel bin rounding, and
  `effective_attempt_time = round1_time + p_round2 * round2_time`.
- BBPSSW success/failure behavior, memory cleanup, and end-to-end-only
  candidate selection.
- Swapping memory selection and endpoint metadata updates.
- Resource reservation boundaries.
- QuantumSavory memory multiplexing: the adapter must install one fixed-slot
  `EntanglerProt` per paired reserved memory lane, and config validation must
  reject paired ranges with different lane counts.

## Integration Tests

Integration tests should run deterministic ideal configurations first, then a
small stochastic seed set, and finally longer statistical comparison jobs marked
as slow.

## Optional Elementary-Link Statistical Tests

Slow elementary-link tests are disabled by default and enabled with
`RUN_SLOW_SIM_TESTS=1`. They isolate one Barrett-Kok elementary link and compare
the observed generation statistics and raw fidelity against the shared theory:

- asymptotic generation rate:
  `expected_rate_hz = p_full / effective_attempt_time_s`;
- mean first-success time:
  `expected_mean_completion_time_s = 1 / expected_rate_hz`;
- raw Bell-state fidelity:
  `derived.barrett_kok_raw_fidelity`.

Each trial runs until the first elementary pair is generated, with a generous
safety timeout. This validates the shared long-run elementary-link rate without
requiring SeQUeNCe's explicit short-circuit event-time distribution to match
QuantumSavory's compressed `EntanglerProt` attempt distribution.

The fast formula tests separately assert the default picosecond milestones
reported in `derived`, including request arrival, protocol start, per-round
emission time, first-round failure time, and two-round completion time. Those
checks are the guard that the compressed QuantumSavory attempt duration remains
anchored to SeQUeNCe's source-level scheduler.

QuantumSavory's optional elementary validation runs both raw-state variants:
`qsavory_exact` with `BarrettKokBellPair` and `qsavory_werner` with
`DepolarizedBellPair(; F=derived.barrett_kok_raw_fidelity)`.

Run SeQUeNCe's optional validation from `sequenceEnv`:

```bash
RUN_SLOW_SIM_TESTS=1 conda run -n sequenceEnv python -m unittest tests.test_sequence_elementary_slow
```

Run QuantumSavory's optional validation:

```bash
RUN_SLOW_SIM_TESTS=1 julia --project=julia/SeQUeNCeQSavoryComparison -e 'using Pkg; Pkg.test()'
```

Both optional tests accept `ELEMENTARY_TEST_TRIALS` and
`ELEMENTARY_TEST_TIMEOUT_S` overrides. The defaults are 300 first-success trials
and a timeout of `20 / expected_rate_hz`, which makes timeout events a failure
guard rather than the statistic being validated.
