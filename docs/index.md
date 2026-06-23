# SeQUeNCe / QuantumSavory Cross Validation

This repository compares the same quantum-network experiment in two simulators:
SeQUeNCe in Python and QuantumSavory in Julia. Both simulators read the same
shared hardware configuration, translate it into simulator-specific objects, and
write the same output schema for seeded statistical comparison.

The source code, issue tracker, and release history are available in the
[GitHub repository](https://github.com/LBacciottini/SeQUeNCe_QSavory_comparison).

The experiment implemented here is the
[SeQUeNCe resource-management tutorial](https://sequence-rtd-tutorial.readthedocs.io/stable/tutorial/chapter4/resource_management.html):
a three-router repeater chain with a short `r1-r2` flow and a long `r1-r3`
flow using elementary generation, swapping, and purification.

## LLM Disclosure

The core QuantumSavory and SeQUeNCe simulations were implemented manually. The
intellectual design of the physics-specific shared configuration, including the
choice of physical parameters and the mapping from shared parameters into
simulator-specific configurations, was also developed manually.

Codex 0.141.0 was used to wire the shared configuration into reusable adapters,
wrap the experiment runners, organize seeded batch and sweep execution, collect
simulation outputs, generate comparison plots, write and expand source
docstrings, and assemble these documentation pages.

The documentation is organized with the [Diátaxis](https://diataxis.fr) structure:

- **Tutorials** teach the workflow through a small guided run.
- **How-to guides** give task-focused commands for running experiments,
  plotting results, validating agreement, and building documentation.
- **Reference** describes the configuration, output schema, simulator mapping,
  tests, vendored simulator snapshots, and generated APIs.
- **Explanation** discusses why the comparison is structured this way and how to
  interpret the modeling choices.

Start with [First Comparison Run](tutorials/first-comparison.md) if you are new
to the project. For the experiment contract and simulator mappings, read the
[Shared Configuration](reference/configuration.md),
[Parameter Mapping](reference/parameter-mapping.md), and
[Cross-Validation Model](explanation/cross-validation-model.md) pages.
