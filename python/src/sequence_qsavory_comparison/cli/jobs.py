"""Process-based job scheduling for simulator batch runners."""

from __future__ import annotations

import csv
import os
import pathlib
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


JOB_FIELDS = (
    "job_id",
    "kind",
    "simulator",
    "seed",
    "link_length_km",
    "config",
    "output",
    "status",
    "returncode",
    "started_at",
    "finished_at",
    "elapsed_s",
    "command",
)


@dataclass(frozen=True)
class Job:
    job_id: str
    kind: str
    simulator: str
    command: list[str]
    config: str = ""
    output: str = ""
    seed: int | None = None
    link_length_km: float | None = None


@dataclass
class JobRecord:
    job: Job
    status: str
    returncode: int | None = None
    started_at: str = ""
    finished_at: str = ""
    elapsed_s: float | str = ""
    process: subprocess.Popen[Any] | None = field(default=None, repr=False)
    started_monotonic: float | None = field(default=None, repr=False)


class JobFailure(RuntimeError):
    """Raised when one or more simulator jobs fail."""


def parse_worker_count(value: str | int | None, *, parallel: bool, job_count: int) -> int:
    """Return the effective worker count for a job batch."""

    if value is None:
        value = "auto" if parallel else "1"
    if isinstance(value, int):
        requested = value
    elif value == "auto":
        requested = max(1, (os.cpu_count() or 1) - 1)
    else:
        requested = int(value)
    if requested <= 0:
        raise ValueError("worker count must be positive")
    return max(1, min(int(job_count), requested)) if job_count else 1


def run_jobs(
    jobs: list[Job],
    *,
    jobs_csv: str | pathlib.Path,
    workers: int,
    prewarm_job: Job | None = None,
) -> list[JobRecord]:
    """Run jobs with bounded process parallelism and fail-fast semantics."""

    records: list[JobRecord] = []
    jobs_csv = pathlib.Path(jobs_csv)
    jobs_csv.parent.mkdir(parents=True, exist_ok=True)

    if prewarm_job is not None:
        prewarm = _run_one(prewarm_job)
        records.append(prewarm)
        if prewarm.returncode != 0:
            _write_jobs_csv(jobs_csv, records)
            raise JobFailure("prewarm job failed")

    pending = list(jobs)
    running: list[JobRecord] = []
    try:
        while pending or running:
            while pending and len(running) < workers:
                record = _start_job(pending.pop(0))
                running.append(record)
                records.append(record)
            failed = _collect_finished(running)
            if failed is not None:
                _terminate_running(running)
                for job in pending:
                    records.append(JobRecord(job=job, status="cancelled"))
                _write_jobs_csv(jobs_csv, records)
                raise JobFailure(f"job {failed.job.job_id} failed with return code {failed.returncode}")
            if running:
                time.sleep(0.1)
    except KeyboardInterrupt:
        _terminate_running(running)
        for job in pending:
            records.append(JobRecord(job=job, status="cancelled"))
        _write_jobs_csv(jobs_csv, records)
        raise

    _write_jobs_csv(jobs_csv, records)
    return records


def _start_job(job: Job) -> JobRecord:
    process = subprocess.Popen(job.command)
    now = _utc_now()
    return JobRecord(
        job=job,
        status="running",
        process=process,
        started_at=now,
        started_monotonic=time.monotonic(),
    )


def _run_one(job: Job) -> JobRecord:
    record = _start_job(job)
    assert record.process is not None
    returncode = record.process.wait()
    _finish_record(record, returncode, "succeeded" if returncode == 0 else "failed")
    return record


def _collect_finished(running: list[JobRecord]) -> JobRecord | None:
    failed: JobRecord | None = None
    still_running: list[JobRecord] = []
    for record in running:
        assert record.process is not None
        returncode = record.process.poll()
        if returncode is None:
            still_running.append(record)
            continue
        _finish_record(record, returncode, "succeeded" if returncode == 0 else "failed")
        if returncode != 0 and failed is None:
            failed = record
    running[:] = still_running
    return failed


def _terminate_running(running: list[JobRecord]) -> None:
    for record in running:
        assert record.process is not None
        if record.process.poll() is None:
            record.process.terminate()
    for record in running:
        assert record.process is not None
        returncode = record.process.wait()
        _finish_record(record, returncode, "terminated")
    running.clear()


def _finish_record(record: JobRecord, returncode: int, status: str) -> None:
    record.status = status
    record.returncode = returncode
    record.finished_at = _utc_now()
    if record.started_monotonic is not None:
        record.elapsed_s = round(time.monotonic() - record.started_monotonic, 6)


def _write_jobs_csv(path: pathlib.Path, records: list[JobRecord]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=JOB_FIELDS)
        writer.writeheader()
        for record in records:
            job = record.job
            writer.writerow(
                {
                    "job_id": job.job_id,
                    "kind": job.kind,
                    "simulator": job.simulator,
                    "seed": "" if job.seed is None else job.seed,
                    "link_length_km": "" if job.link_length_km is None else job.link_length_km,
                    "config": job.config,
                    "output": job.output,
                    "status": record.status,
                    "returncode": "" if record.returncode is None else record.returncode,
                    "started_at": record.started_at,
                    "finished_at": record.finished_at,
                    "elapsed_s": record.elapsed_s,
                    "command": shlex.join(job.command),
                }
            )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
