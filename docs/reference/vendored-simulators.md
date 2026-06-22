# Vendored Simulators

The release repository includes simulator snapshots under `dev/` so public
commands do not depend on ignored agent assets.

## SeQUeNCe

The Python adapter imports SeQUeNCe from:

```text
dev/SeQUeNCe
```

The shared config records this path as `paths.sequence_path`.

## QuantumSavory

The Julia package depends on:

```text
dev/QuantumSavory.jl
```

The Julia package project pins this dependency through its `[sources]` entry,
and the shared config records the same path as `paths.quantumsavory_path`.

The vendored QuantumSavory snapshot is the source tree that contains the
`BBPSSWProt` implementation used by this comparison.
