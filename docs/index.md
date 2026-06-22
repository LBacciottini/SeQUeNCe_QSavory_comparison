# SeQUeNCe / QuantumSavory Cross Validation

This repository compares the same quantum-network experiment in two simulators:
SeQUeNCe in Python and QuantumSavory in Julia. Both simulators read the same
shared hardware configuration, translate it into simulator-specific objects, and
write the same output schema for seeded statistical comparison.

The documentation is organized with the [Diátaxis](https://diataxis.fr) structure:

- **Tutorials** teach the workflow through a small guided run.
- **How-to guides** give task-focused commands for running experiments,
  plotting results, validating agreement, and building documentation.
- **Reference** describes the configuration, output schema, simulator mapping,
  tests, vendored simulator snapshots, and generated APIs.
- **Explanation** discusses why the comparison is structured this way and how to
  interpret the modeling choices.

Start with [First Comparison Run](tutorials/first-comparison.md) if you are new
to the project. Reviewers should start with the
[Shared Configuration](reference/configuration.md) and
[Parameter Mapping](reference/parameter-mapping.md) references, then read the
[Cross-Validation Model](explanation/cross-validation-model.md).
