# Diagnostic Methodology

The diagnostics are designed to answer one question at a time: where is the
first layer at which SeQUeNCe and QuantumSavory stop describing the same
experiment?

They are not a replacement for the production sweep runner. Production sweeps
answer whether final outputs agree. Diagnostics answer why they agree or
disagree.

They are also the validation scaffold for the comparison. The project does not
only ask whether the final completion-time and fidelity curves are close; it
checks that the two simulator adapters match in every sub-step used to build
those curves. A full-run match is convincing only after elementary generation,
memory multiplexing, contention, swapping, purification, and completion
accounting have each been validated in isolation.

## Layered Attribution

The comparison is built from a stack of model layers:

1. elementary Barrett-Kok generation on one reserved memory lane;
2. memory multiplexing on one elementary link;
3. contention between flows sharing the same midpoint BSM;
4. two elementary links feeding an ideal swap;
5. end-to-end swapped pair supply without purification;
6. end-to-end BBPSSW purification and completion accounting.

The diagnostic scenarios mirror that stack. This matters because a later
scenario can amplify an earlier mismatch. A completion-time gap in the full
scenario is not evidence that BBPSSW is wrong until elementary supply and swap
delivery have been checked.

## Common Event Schema

Each simulator writes diagnostic events with the same high-level fields:

- simulator label;
- seed;
- scenario;
- stage and event name;
- event time in seconds;
- optional flow, link, node, slot, pair identifier, and JSON details.

The analyzer reduces those events to terminal times and event counts per
stage. Terminal time means the last observed timestamp for a
`(simulator, seed, scenario, stage, event)` group. For fill-time diagnostics,
that is the meaningful quantity: how long it took to produce the observed
count.

## Confidence Intervals Before Mechanisms

The first pass is statistical. For each stage/event, compare means and
confidence intervals across seeds. If confidence intervals overlap and event
counts match, do not infer a mechanism from a small mean difference.

If confidence intervals do not overlap, inspect the earliest divergent
scenario. Only then should you read simulator-specific traces or add narrower
instrumentation.

## The BBPSSW Lesson

The BBPSSW investigation is a useful example of why this discipline matters.
Elementary generation and swap-only diagnostics were not enough to explain the
full completion-time gap. Counting supplied end-to-end pairs showed that the
simulators consumed different numbers of raw end-to-end pairs before reaching
the same completion definition.

The next check was the BBPSSW success probability. For the default Werner
configuration, the swapped end-to-end pair has:

```text
F_e2e = 0.9557506566
```

Ideal BBPSSW on two identical Werner pairs therefore has:

```text
p_success = 0.9427413238
F_output  = 0.9691702809
```

QuantumSavory Werner matched that success probability. SeQUeNCe's stock
circuit purifier did not, because it samples local circuit measurement
outcomes under a different state representation. SeQUeNCe's Bell-diagonal
purifier has the right equations, but the Bell-diagonal quantum manager cannot
run the physical Barrett-Kok BSM stack used for elementary generation.

The adapter therefore keeps SeQUeNCe's normal Barrett-Kok generation stack and
registers `comparison_werner_bbpssw` only for purification. That protocol uses
the analytical Werner BBPSSW success probability and output fidelity while
preserving SeQUeNCe resource-manager reservations, messages, memory updates,
and timing.

## What To Preserve

When adding a new diagnostic, keep it reduced and falsifiable:

- isolate one model layer;
- write events in the common schema;
- compare event counts and confidence intervals;
- document the simulator-specific mechanism only after the reduced test
  identifies the divergent layer.

The goal is not to make the simulators internally identical. The goal is to
prove that the simulator-specific implementation of each configured layer has
the same experiment-level semantics.
