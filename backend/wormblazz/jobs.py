from __future__ import annotations

import asyncio
import uuid
from typing import Awaitable, Callable

from .crawlers import ProgressCallback
from .models import CrawlJob, JobStatus

# A job body receives a progress callback and returns the finished network id.
JobFactory = Callable[[ProgressCallback], Awaitable[str]]


class JobManager:
    """
    In-memory background job runner backed by the FastAPI event loop.

    Jobs live only for the lifetime of the process; the crawled network itself
    is persisted through NetworkCache, so a finished job's data survives even
    after the job record is dropped.
    """

    def __init__(self, max_jobs: int = 200) -> None:
        self._jobs: dict[str, CrawlJob] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._max_jobs = max_jobs

    def submit(self, factory: JobFactory) -> CrawlJob:
        job = CrawlJob(job_id=uuid.uuid4().hex, status=JobStatus.QUEUED)
        self._jobs[job.job_id] = job
        self._prune()

        def report(message: str, fraction: float) -> None:
            job.message = message
            job.progress = max(0.0, min(1.0, fraction))
            if job.status is JobStatus.QUEUED:
                job.status = JobStatus.RUNNING

        async def runner() -> None:
            job.status = JobStatus.RUNNING
            try:
                job.network_id = await factory(report)
                job.status = JobStatus.SUCCEEDED
                job.progress = 1.0
                if not job.message:
                    job.message = "Done"
            except Exception as error:  # noqa: BLE001 - surfaced to the client
                job.status = JobStatus.FAILED
                job.error = str(error) or error.__class__.__name__

        self._tasks[job.job_id] = asyncio.create_task(runner())
        return job

    def get(self, job_id: str) -> CrawlJob | None:
        return self._jobs.get(job_id)

    def _prune(self) -> None:
        if len(self._jobs) <= self._max_jobs:
            return
        finished = [
            job_id
            for job_id, job in self._jobs.items()
            if job.status in {JobStatus.SUCCEEDED, JobStatus.FAILED}
        ]
        for job_id in finished[: len(self._jobs) - self._max_jobs]:
            self._jobs.pop(job_id, None)
            self._tasks.pop(job_id, None)
