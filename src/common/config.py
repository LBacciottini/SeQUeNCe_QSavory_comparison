"""Load and validate the shared TOML experiment configuration."""

from __future__ import annotations

import copy
import pathlib
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - for Python < 3.11 only
    tomllib = None
from typing import Any

from .models import derive_parameters, require_finite_derived


REQUIRED_SECTIONS = (
    "experiment",
    "paths",
    "topology",
    "memories",
    "optics",
    "detectors",
    "barrett_kok",
    "resource_reservation",
    "purification",
    "swapping",
    "outputs",
)


def load_config(path: str | pathlib.Path) -> dict[str, Any]:
    """Read a TOML config file into plain Python dictionaries."""

    config_path = pathlib.Path(path)
    if tomllib is not None:
        with config_path.open("rb") as handle:
            return tomllib.load(handle)
    return _parse_minimal_toml(config_path.read_text(encoding="utf-8"))


def _parse_minimal_toml(text: str) -> dict[str, Any]:
    """Parse the small TOML subset used by `configs/default.toml`.

    This fallback keeps Python 3.9 usable without an extra `tomli` dependency.
    It intentionally supports only tables, strings, booleans, integers, floats,
    and one-line arrays of those scalar types.
    """

    root: dict[str, Any] = {}
    current = root
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current = root
            for part in line[1:-1].split("."):
                current = current.setdefault(part, {})
            continue
        if "=" not in line:
            raise ValueError(f"invalid TOML line {line_no}: {raw_line!r}")
        key, value = [part.strip() for part in line.split("=", 1)]
        current[key] = _parse_minimal_toml_value(value)
    return root


def _parse_minimal_toml_value(value: str) -> Any:
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value in ("true", "false"):
        return value == "true"
    if value.startswith("[") and value.endswith("]"):
        body = value[1:-1].strip()
        if not body:
            return []
        return [_parse_minimal_toml_value(part.strip()) for part in body.split(",")]
    try:
        if any(marker in value for marker in (".", "e", "E")):
            return float(value)
        return int(value)
    except ValueError as exc:
        raise ValueError(f"unsupported TOML value {value!r}") from exc


def _prob(config: dict[str, Any], section: str, key: str) -> None:
    value = float(config[section][key])
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{section}.{key} must be in [0, 1], got {value!r}")


def _positive(config: dict[str, Any], section: str, key: str) -> None:
    value = float(config[section][key])
    if value <= 0.0:
        raise ValueError(f"{section}.{key} must be positive, got {value!r}")


def _slot_range(name: str, value: Any, count: int) -> tuple[int, int]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name} must be a two-element inclusive slot range")
    lo, hi = int(value[0]), int(value[1])
    if lo < 0 or hi < lo or hi >= count:
        raise ValueError(f"{name}={value!r} is outside memory count {count}")
    return lo, hi


def _overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return max(a[0], b[0]) <= min(a[1], b[1])


def _slot_count(slot_range: tuple[int, int]) -> int:
    return slot_range[1] - slot_range[0] + 1


def validate_config(config: dict[str, Any]) -> None:
    """Validate fields that are required by both simulator adapters."""

    for section in REQUIRED_SECTIONS:
        if section not in config:
            raise ValueError(f"missing required config section [{section}]")

    _positive(config, "experiment", "runtime_s")
    _positive(config, "topology", "link_length_km")
    _positive(config, "topology", "signal_speed_km_per_s")
    _positive(config, "optics", "quantum_channel_frequency_hz")
    _positive(config, "detectors", "count_rate_hz")
    if "degradation" in config["swapping"]:
        raise ValueError("swapping.degradation is not supported; swaps are ideal in this comparison")
    for section, key in (
        ("memories", "emission_efficiency"),
        ("optics", "collection_efficiency"),
        ("optics", "frequency_conversion_efficiency"),
        ("detectors", "efficiency"),
        ("detectors", "dark_count_probability"),
        ("barrett_kok", "mode_matching_visibility"),
        ("swapping", "success_probability"),
    ):
        _prob(config, section, key)

    if config["barrett_kok"]["success_probability_model"] != "p_det_squared_over_2":
        raise ValueError("only barrett_kok.success_probability_model='p_det_squared_over_2' is supported")

    counts = {
        "r1": int(config["memories"]["r1_count"]),
        "r2": int(config["memories"]["r2_count"]),
        "r3": int(config["memories"]["r3_count"]),
    }
    reservation = config["resource_reservation"]
    flow1 = reservation["flow1"]
    flow2 = reservation["flow2"]

    r1_f1 = _slot_range("flow1.r1_slots", flow1["r1_slots"], counts["r1"])
    r2_f1 = _slot_range("flow1.r2_slots", flow1["r2_slots"], counts["r2"])
    r1_f2 = _slot_range("flow2.r1_slots", flow2["r1_slots"], counts["r1"])
    r2_left = _slot_range("flow2.r2_left_slots", flow2["r2_left_slots"], counts["r2"])
    r2_right = _slot_range("flow2.r2_right_slots", flow2["r2_right_slots"], counts["r2"])
    r3_f2 = _slot_range("flow2.r3_slots", flow2["r3_slots"], counts["r3"])

    if _overlap(r1_f1, r1_f2):
        raise ValueError("r1 flow1 and flow2 reservations overlap")
    if _overlap(r2_f1, r2_left) or _overlap(r2_f1, r2_right) or _overlap(r2_left, r2_right):
        raise ValueError("r2 memory reservations overlap")

    if _slot_count(r1_f1) != _slot_count(r2_f1):
        raise ValueError("flow1 r1/r2 reservations must have the same lane count")
    if _slot_count(r1_f2) != _slot_count(r2_left):
        raise ValueError("flow2 left-link r1/r2 reservations must have the same lane count")
    if _slot_count(r2_right) != _slot_count(r3_f2):
        raise ValueError("flow2 right-link r2/r3 reservations must have the same lane count")

    if int(flow1["target_pairs"]) > r1_f1[1] - r1_f1[0] + 1:
        raise ValueError("flow1 target_pairs exceeds reserved r1 slots")
    if int(flow2["target_pairs"]) > r1_f2[1] - r1_f2[0] + 1:
        raise ValueError("flow2 target_pairs exceeds reserved r1 slots")


def resolve_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return a deep-copied config with a simulator-agnostic `derived` section."""

    validate_config(config)
    resolved = copy.deepcopy(config)
    derived = derive_parameters(resolved)
    require_finite_derived(derived)
    resolved["derived"] = derived
    return resolved
