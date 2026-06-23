"""Run a tiered diagnostic campaign across scenarios, simulators, and seeds."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from sequence_qsavory_comparison.common.diagnostics import DIAGNOSTIC_SCHEMA_VERSION, SCENARIOS

from .jobs import Job, JobFailure, parse_worker_count, run_jobs
from .run_batch import _julia_prewarm_job, _parse_seeds, _parse_simulators, _repo_root


def _parse_scenarios(spec: str) -> list[str]:
    if spec == "smoke":
        return ["single_lane_elementary", "same_link_multilane", "eg_swap_no_purification", "full_reduced"]
    if spec == "all":
        return list(SCENARIOS)
    scenarios = [item.strip() for item in spec.split(",") if item.strip()]
    unknown = sorted(set(scenarios) - set(SCENARIOS))
    if unknown:
        raise ValueError(f"unknown diagnostic scenario(s): {', '.join(unknown)}")
    return scenarios


def _diagnostic_command(root: pathlib.Path, config: str, seed: int, scenario: str, simulator: str, output: pathlib.Path, raw_state_model: str = "exact") -> list[str]:
    command = [
        sys.executable,
        str(root / "scripts" / "run_diagnostic.py"),
        "--config",
        config,
        "--seed",
        str(seed),
        "--scenario",
        scenario,
        "--simulator",
        simulator,
        "--output",
        str(output),
    ]
    if simulator == "qsavory":
        command.extend(["--raw-state-model", raw_state_model])
    return command


def _build_jobs(config: str, seeds: list[int], scenarios: list[str], simulators: set[str], out_root: pathlib.Path, root: pathlib.Path) -> list[Job]:
    jobs: list[Job] = []
    for scenario in scenarios:
        for seed in seeds:
            if "sequence" in simulators:
                output = out_root / scenario / "sequence" / f"seed_{seed}"
                jobs.append(Job(job_id=f"{scenario}_sequence_seed_{seed}", kind="diagnostic", simulator="sequence", seed=seed, config=config, output=str(output), command=_diagnostic_command(root, config, seed, scenario, "sequence", output)))
            if "qsavory" in simulators:
                for model in ("exact", "werner"):
                    simulator = f"qsavory_{model}"
                    output = out_root / scenario / simulator / f"seed_{seed}"
                    jobs.append(Job(job_id=f"{scenario}_{simulator}_seed_{seed}", kind="diagnostic", simulator=simulator, seed=seed, config=config, output=str(output), command=_diagnostic_command(root, config, seed, scenario, "qsavory", output, model)))
    return jobs


def _write_manifest(path: pathlib.Path, *, config: str, seeds: list[int], scenarios: list[str], simulators: set[str], workers: int) -> None:
    manifest = {
        "schema_version": DIAGNOSTIC_SCHEMA_VERSION,
        "layout_version": 1,
        "config": config,
        "seeds": seeds,
        "scenarios": scenarios,
        "simulators": sorted(simulators),
        "workers": workers,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="shared/configs/default.toml")
    parser.add_argument("--seeds", default="1:3")
    parser.add_argument("--scenarios", default="smoke", help="'smoke', 'all', or comma-separated scenario names")
    parser.add_argument("--simulators", default="sequence,qsavory")
    parser.add_argument("--output", required=True)
    parser.add_argument("--workers", default=None)
    parser.add_argument("--parallel", action="store_true")
    parser.add_argument("--julia-prewarm", dest="julia_prewarm", action="store_true", default=True)
    parser.add_argument("--no-julia-prewarm", dest="julia_prewarm", action="store_false")
    args = parser.parse_args()

    root = _repo_root()
    out_root = pathlib.Path(args.output)
    seeds = _parse_seeds(args.seeds)
    scenarios = _parse_scenarios(args.scenarios)
    simulators = _parse_simulators(args.simulators)
    jobs = _build_jobs(args.config, seeds, scenarios, simulators, out_root, root)
    workers = parse_worker_count(args.workers, parallel=args.parallel, job_count=len(jobs))
    prewarm = _julia_prewarm_job(root) if args.julia_prewarm and any(job.simulator.startswith("qsavory") for job in jobs) and workers > 1 else None
    _write_manifest(out_root / "diagnostic_campaign_manifest.json", config=args.config, seeds=seeds, scenarios=scenarios, simulators=simulators, workers=workers)
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
