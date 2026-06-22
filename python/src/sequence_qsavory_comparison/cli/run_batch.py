"""Run one or both simulators for a range of seeds.

The batch CLI creates one job per ``(simulator variant, seed)`` pair.  SeQUeNCe
produces the ``sequence`` series, while QuantumSavory is run twice by default:
once with the exact Barrett-Kok raw state and once with the Werner/depolarized
raw-state abstraction.  Each job writes a canonical run directory containing
``manifest.json``, ``pairs.csv``, and ``summary.csv``.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from .jobs import Job, JobFailure, parse_worker_count, run_jobs

QSAVORY_RAW_STATE_MODELS = ("exact", "werner")


def _repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[4]


def _parse_seeds(spec: str) -> list[int]:
    if ":" in spec:
        start, stop = [int(part) for part in spec.split(":", 1)]
        return list(range(start, stop + 1))
    return [int(part) for part in spec.split(",") if part]


def _parse_simulators(spec: str) -> set[str]:
    return {item.strip() for item in spec.split(",") if item.strip()}


def _julia_project(root: pathlib.Path) -> pathlib.Path:
    return root / "julia" / "SeQUeNCeQSavoryComparison"


def _sequence_command(root: pathlib.Path, config: str, seed: int, output: pathlib.Path) -> list[str]:
    return [
        sys.executable,
        str(root / "scripts" / "run_sequence.py"),
        "--config",
        config,
        "--seed",
        str(seed),
        "--output",
        str(output),
    ]


def _qsavory_command(root: pathlib.Path, config: str, seed: int, raw_state_model: str, output: pathlib.Path) -> list[str]:
    return [
        "julia",
        f"--project={_julia_project(root)}",
        str(root / "scripts" / "run_qsavory.jl"),
        "--config",
        config,
        "--seed",
        str(seed),
        "--raw-state-model",
        raw_state_model,
        "--output",
        str(output),
    ]


def _julia_prewarm_job(root: pathlib.Path) -> Job:
    return Job(
        job_id="julia_prewarm",
        kind="julia_prewarm",
        simulator="qsavory",
        command=[
            "julia",
            f"--project={_julia_project(root)}",
            "-e",
            "using Pkg; Pkg.instantiate(); Pkg.precompile(); using SeQUeNCeQSavoryComparison",
        ],
    )


def _build_jobs(config_path: str, seeds: list[int], simulators: set[str], out_root: pathlib.Path, root: pathlib.Path) -> list[Job]:
    jobs: list[Job] = []
    for seed in seeds:
        if "sequence" in simulators:
            output = out_root / "sequence" / f"seed_{seed}"
            jobs.append(
                Job(
                    job_id=f"sequence_seed_{seed}",
                    kind="simulation",
                    simulator="sequence",
                    seed=seed,
                    config=config_path,
                    output=str(output),
                    command=_sequence_command(root, config_path, seed, output),
                )
            )
        if "qsavory" in simulators:
            for raw_state_model in QSAVORY_RAW_STATE_MODELS:
                simulator = f"qsavory_{raw_state_model}"
                output = out_root / simulator / f"seed_{seed}"
                jobs.append(
                    Job(
                        job_id=f"{simulator}_seed_{seed}",
                        kind="simulation",
                        simulator=simulator,
                        seed=seed,
                        config=config_path,
                        output=str(output),
                        command=_qsavory_command(root, config_path, seed, raw_state_model, output),
                    )
                )
    return jobs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="shared/configs/default.toml")
    parser.add_argument("--seeds", required=True, help="Comma list or inclusive start:stop range")
    parser.add_argument("--output", required=True)
    parser.add_argument("--simulators", default="sequence,qsavory")
    parser.add_argument("--workers", default=None, help="Worker count or 'auto'; default is 1 unless --parallel is set")
    parser.add_argument("--parallel", action="store_true", help="Shortcut for --workers auto")
    parser.add_argument("--julia-prewarm", dest="julia_prewarm", action="store_true", default=True)
    parser.add_argument("--no-julia-prewarm", dest="julia_prewarm", action="store_false")
    args = parser.parse_args()

    out_root = pathlib.Path(args.output)
    out_root.mkdir(parents=True, exist_ok=True)
    simulators = _parse_simulators(args.simulators)
    root = _repo_root()
    seeds = _parse_seeds(args.seeds)
    jobs = _build_jobs(args.config, seeds, simulators, out_root, root)
    workers = parse_worker_count(args.workers, parallel=args.parallel, job_count=len(jobs))
    has_qsavory = any(job.simulator.startswith("qsavory") for job in jobs)
    prewarm = _julia_prewarm_job(root) if args.julia_prewarm and has_qsavory and workers > 1 else None
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
