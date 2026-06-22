"""Run seeded simulator batches while sweeping elementary-link length."""

from __future__ import annotations

import argparse
import copy
import json
import pathlib
import sys
from datetime import datetime, timezone

from sequence_qsavory_comparison.common.config import load_config, write_config

from .jobs import Job, JobFailure, parse_worker_count, run_jobs
from .run_batch import (
    QSAVORY_RAW_STATE_MODELS,
    _julia_prewarm_job,
    _parse_seeds,
    _parse_simulators,
    _qsavory_command,
    _repo_root,
    _sequence_command,
)

DEFAULT_LINK_LENGTHS_KM = (5.0, 10.0, 20.0, 30.0, 40.0)


def _parse_link_lengths(spec: str) -> list[float]:
    if ":" in spec:
        parts = [float(part) for part in spec.split(":")]
        if len(parts) != 3:
            raise ValueError("range link-length syntax is start:stop:step")
        start, stop, step = parts
        if step <= 0:
            raise ValueError("link-length range step must be positive")
        values: list[float] = []
        current = start
        while current <= stop + step * 1e-12:
            values.append(round(current, 12))
            current += step
        return values
    return [float(part) for part in spec.split(",") if part]


def _link_dir_name(length_km: float) -> str:
    if float(length_km).is_integer():
        return f"link_{int(length_km):03d}km"
    label = f"{length_km:.6g}".replace(".", "p")
    return f"link_{label}km"


def _write_sweep_manifest(
    path: pathlib.Path,
    *,
    config_path: str,
    link_lengths: list[float],
    seeds: list[int],
    simulators: set[str],
    workers: int,
    julia_prewarm: bool,
) -> None:
    manifest = {
        "schema_version": 1,
        "layout_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "base_config": config_path,
        "sweep_parameter": "topology.link_length_km",
        "link_lengths_km": link_lengths,
        "seeds": seeds,
        "simulators": sorted(simulators),
        "workers": workers,
        "julia_prewarm": julia_prewarm,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _build_jobs(
    link_lengths: list[float],
    seeds: list[int],
    simulators: set[str],
    out_root: pathlib.Path,
    root: pathlib.Path,
) -> tuple[list[Job], dict[float, pathlib.Path]]:
    jobs: list[Job] = []
    config_paths: dict[float, pathlib.Path] = {}
    for link_length in link_lengths:
        length_root = out_root / _link_dir_name(link_length)
        generated_config = length_root / "config.toml"
        config_paths[link_length] = generated_config
        for seed in seeds:
            if "sequence" in simulators:
                output = length_root / "sequence" / f"seed_{seed}"
                jobs.append(
                    Job(
                        job_id=f"link_{_link_dir_name(link_length)}_sequence_seed_{seed}",
                        kind="simulation",
                        simulator="sequence",
                        seed=seed,
                        link_length_km=link_length,
                        config=str(generated_config),
                        output=str(output),
                        command=_sequence_command(root, str(generated_config), seed, output),
                    )
                )
            if "qsavory" in simulators:
                for raw_state_model in QSAVORY_RAW_STATE_MODELS:
                    simulator = f"qsavory_{raw_state_model}"
                    output = length_root / simulator / f"seed_{seed}"
                    jobs.append(
                        Job(
                            job_id=f"link_{_link_dir_name(link_length)}_{simulator}_seed_{seed}",
                            kind="simulation",
                            simulator=simulator,
                            seed=seed,
                            link_length_km=link_length,
                            config=str(generated_config),
                            output=str(output),
                            command=_qsavory_command(root, str(generated_config), seed, raw_state_model, output),
                        )
                    )
    return jobs, config_paths


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="shared/configs/default.toml")
    parser.add_argument("--link-lengths", default=",".join(str(value).rstrip("0").rstrip(".") for value in DEFAULT_LINK_LENGTHS_KM))
    parser.add_argument("--seeds", required=True, help="Comma list or inclusive start:stop range")
    parser.add_argument("--output", required=True)
    parser.add_argument("--simulators", default="sequence,qsavory")
    parser.add_argument("--workers", default=None, help="Worker count or 'auto'; default is 1 unless --parallel is set")
    parser.add_argument("--parallel", action="store_true", help="Shortcut for --workers auto")
    parser.add_argument("--julia-prewarm", dest="julia_prewarm", action="store_true", default=True)
    parser.add_argument("--no-julia-prewarm", dest="julia_prewarm", action="store_false")
    args = parser.parse_args()

    base_config = load_config(args.config)
    link_lengths = _parse_link_lengths(args.link_lengths)
    seeds = _parse_seeds(args.seeds)
    simulators = _parse_simulators(args.simulators)
    out_root = pathlib.Path(args.output)
    out_root.mkdir(parents=True, exist_ok=True)
    root = _repo_root()
    jobs, config_paths = _build_jobs(link_lengths, seeds, simulators, out_root, root)
    workers = parse_worker_count(args.workers, parallel=args.parallel, job_count=len(jobs))
    has_qsavory = any(job.simulator.startswith("qsavory") for job in jobs)
    prewarm = _julia_prewarm_job(root) if args.julia_prewarm and has_qsavory and workers > 1 else None
    _write_sweep_manifest(
        out_root / "sweep_manifest.json",
        config_path=args.config,
        link_lengths=link_lengths,
        seeds=seeds,
        simulators=simulators,
        workers=workers,
        julia_prewarm=prewarm is not None,
    )

    for link_length in link_lengths:
        sweep_config = copy.deepcopy(base_config)
        sweep_config["topology"]["link_length_km"] = link_length
        write_config(config_paths[link_length], sweep_config)
    try:
        run_jobs(jobs, jobs_csv=out_root / "jobs.csv", workers=workers, prewarm_job=prewarm)
    except JobFailure as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


def run() -> None:
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
