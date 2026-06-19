"""Shared theory checks for optional elementary-link validation tests."""

from __future__ import annotations

import math
import statistics
from typing import Any

from .config import resolve_config


def elementary_rate_theory(config: dict[str, Any]) -> dict[str, float]:
    """Return asymptotic elementary-link generation-rate expectations."""

    resolved = resolve_config(config)
    derived = resolved["derived"]
    return {
        "attempt_success_probability": float(derived["barrett_kok_full_success_probability"]),
        "effective_attempt_time_s": float(derived["barrett_kok_effective_attempt_time_s"]),
        "round2_entry_probability": float(derived["barrett_kok_round2_entry_probability"]),
        "round1_time_s": float(derived["barrett_kok_round1_time_s"]),
        "round2_time_s": float(derived["barrett_kok_round2_time_s"]),
        "expected_rate_hz": float(derived["barrett_kok_expected_rate_hz"]),
        "expected_mean_completion_time_s": 1.0 / float(derived["barrett_kok_expected_rate_hz"]),
        "expected_raw_fidelity": float(derived["barrett_kok_raw_fidelity"]),
    }


def mean_acceptance_interval(samples: list[float], sigma: float = 5.0) -> tuple[float, float]:
    """Return a conservative normal-approximation interval for a sample mean."""

    if not samples:
        raise ValueError("at least one sample is required")
    mean = statistics.fmean(samples)
    if len(samples) == 1:
        return mean, mean
    standard_error = statistics.stdev(samples) / math.sqrt(len(samples))
    return mean - sigma * standard_error, mean + sigma * standard_error


def assert_mean_completion_time(
    name: str,
    completion_times_s: list[float],
    expected_mean_s: float,
    sigma: float = 5.0,
) -> None:
    """Raise `AssertionError` if an observed mean completion time is off theory."""

    lo, hi = mean_acceptance_interval(completion_times_s, sigma=sigma)
    if not lo <= expected_mean_s <= hi:
        observed_mean = statistics.fmean(completion_times_s) if completion_times_s else float("nan")
        raise AssertionError(
            f"{name}: observed mean completion time {observed_mean:.6g}s, "
            f"expected {expected_mean_s:.6g}s, accepted interval [{lo:.6g}, {hi:.6g}]"
        )
