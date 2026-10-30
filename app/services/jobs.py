"""In-memory background job manager for CPU-intensive calculations."""
from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

JOB_RETENTION_SECONDS = 3600  # 1 hour
MAX_JOBS = 200

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="job-runner")
_lock = threading.Lock()


@dataclass
class Job:
    id: str
    job_type: str
    status: str = "pending"  # "pending" | "running" | "completed" | "failed"
    progress: int = 0  # 0 to 100
    message: str = "Job queued"
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_jobs: dict[str, Job] = {}


def _cleanup_old_jobs_locked() -> None:
    now = time.time()
    to_delete = []
    for job_id, job in _jobs.items():
        if job.completed_at and (now - job.completed_at > JOB_RETENTION_SECONDS):
            to_delete.append(job_id)
    for jid in to_delete:
        del _jobs[jid]

    # If still too many jobs, remove oldest completed/failed jobs
    if len(_jobs) > MAX_JOBS:
        sorted_jobs = sorted(
            [j for j in _jobs.values() if j.status in ("completed", "failed")],
            key=lambda j: j.created_at,
        )
        excess = len(_jobs) - MAX_JOBS
        for j in sorted_jobs[:excess]:
            _jobs.pop(j.id, None)


def submit_job(
    job_type: str,
    worker_fn: Callable[[Callable[[int, str], None]], Any],
) -> str:
    """Submit a task to run in the background thread pool.

    `worker_fn` will be passed a `progress_cb(pct: int, msg: str = "")` callback.
    """
    job_id = str(uuid.uuid4())
    job = Job(id=job_id, job_type=job_type)

    with _lock:
        _cleanup_old_jobs_locked()
        _jobs[job_id] = job

    def runner() -> None:
        def update_progress(pct: int, msg: str = "") -> None:
            with _lock:
                if job_id in _jobs:
                    _jobs[job_id].progress = max(0, min(100, int(pct)))
                    if msg:
                        _jobs[job_id].message = msg
                    if _jobs[job_id].status == "pending":
                        _jobs[job_id].status = "running"

        with _lock:
            if job_id in _jobs:
                _jobs[job_id].status = "running"
                _jobs[job_id].message = "Running..."

        try:
            res = worker_fn(update_progress)
            with _lock:
                if job_id in _jobs:
                    _jobs[job_id].status = "completed"
                    _jobs[job_id].progress = 100
                    _jobs[job_id].message = "Completed"
                    _jobs[job_id].result = res
                    _jobs[job_id].completed_at = time.time()
        except Exception as exc:
            logger.exception("Job %s (%s) failed: %s", job_id, job_type, exc)
            with _lock:
                if job_id in _jobs:
                    _jobs[job_id].status = "failed"
                    _jobs[job_id].error = str(exc)
                    _jobs[job_id].message = f"Failed: {exc}"
                    _jobs[job_id].completed_at = time.time()

    _executor.submit(runner)
    return job_id


def get_job(job_id: str) -> Optional[dict[str, Any]]:
    """Return job dictionary or None if not found."""
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return None
        return job.to_dict()


def clear_all_jobs() -> None:
    """Clear all registered jobs (useful for test resets)."""
    with _lock:
        _jobs.clear()
