# Exact and Werner Models

QuantumSavory is run twice for each seed.

The `qsavory_exact` series uses the analytical Barrett-Kok state class. This
keeps detector efficiency, dark-count probability, arm transmissivity, parity,
and mode-matching visibility inside the raw state model.
The exact density matrix and raw-fidelity formula are derived in
[Barrett-Kok State Model](barrett-kok-state.md).

The `qsavory_werner` series uses a depolarized Bell-pair approximation with the
same raw fidelity:

```text
DepolarizedBellPair(; F=derived.barrett_kok_raw_fidelity)
```

The two variants share the same generation rate and raw-fidelity target, but
they do not preserve the same density matrix. Plotting both variants shows
whether the simpler Werner approximation tracks SeQUeNCe as closely as the
exact Barrett-Kok state model.
