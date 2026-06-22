"""Manifest and CSV output helpers shared by simulator runners.

The comparison outputs are deliberately language agnostic. Both Python and
Julia runners write equivalent manifests, pair tables, and summary tables so
downstream plotting and validation code can read either simulator without
special cases.
"""

from __future__ import annotations

import csv
import json
import pathlib
from datetime import datetime, timezone
from typing import Any, Iterable


PAIR_FIELDS = (
    "simulator",
    "seed",
    "flow",
    "local_node",
    "local_slot",
    "remote_node",
    "remote_slot",
    "pair_id",
    "delivery_time_s",
    "fidelity",
    "status",
)

SUMMARY_FIELDS = (
    "simulator",
    "seed",
    "status",
    "runtime_s",
    "completion_time_s",
    "target_pairs",
    "target_completed",
    "flow1_delivered",
    "flow2_delivered",
    "flow1_mean_fidelity",
    "flow2_mean_fidelity",
)


def utc_now_iso() -> str:
    """Return an ISO-8601 UTC timestamp suitable for manifests.

    Returns:
        Timezone-aware timestamp string.
    """

    return datetime.now(timezone.utc).isoformat()


def ensure_output_dir(path: str | pathlib.Path) -> pathlib.Path:
    """Create and return an output directory.

    Args:
        path: Directory to create.

    Returns:
        `Path` object for the created directory.
    """

    out = pathlib.Path(path)
    out.mkdir(parents=True, exist_ok=True)
    return out


def write_manifest(path: str | pathlib.Path, manifest: dict[str, Any]) -> None:
    """Write the language-agnostic manifest as stable pretty JSON.

    Args:
        path: Destination JSON path.
        manifest: Manifest dictionary containing raw config, resolved config,
            applied simulator config, seed metadata, and output locations.
    """

    with pathlib.Path(path).open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_pairs_csv(path: str | pathlib.Path, rows: Iterable[dict[str, Any]]) -> None:
    """Write per-pair result rows using the canonical comparison schema.

    Missing fields are written as empty cells so callers can supply partial
    dictionaries while preserving the public CSV header.

    Args:
        path: Destination CSV path.
        rows: Iterable of pair dictionaries keyed by `PAIR_FIELDS`.
    """

    with pathlib.Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAIR_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in PAIR_FIELDS})


def write_summary_csv(path: str | pathlib.Path, rows: Iterable[dict[str, Any]]) -> None:
    """Write one summary row per simulator run.

    Args:
        path: Destination CSV path.
        rows: Iterable of run-summary dictionaries keyed by `SUMMARY_FIELDS`.
    """

    with pathlib.Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in SUMMARY_FIELDS})
