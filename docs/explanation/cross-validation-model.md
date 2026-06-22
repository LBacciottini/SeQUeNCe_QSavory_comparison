# Cross-Validation Model

The project treats the shared TOML configuration as the experiment contract.
Neither simulator is allowed to invent hardware parameters outside that
contract. Each adapter maps the shared configuration into its simulator's native
objects and records the realized mapping in `manifest.json`.

This design makes the comparison auditable:

- authored values live in `raw_config`;
- checked and derived values live in `resolved_config`;
- simulator-specific values live in `applied_config`;
- metrics are written in common CSV schemas.

Agreement between the simulators is therefore judged at the level of the shared
experiment: completion time, delivered pairs, and fidelity metrics under the
same hardware assumptions.
