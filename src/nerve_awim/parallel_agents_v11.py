"""Bounded in-process parallel subagents for NERVE research.

Worker functions must be explicitly registered trusted local callables.
No external agent execution, network access, hard timeout, process sandbox,
live device control, or permission to bypass review is provided.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from time import perf_counter
from types import MappingProxyType


@dataclass(frozen=True)
class AgentJob:
    job_id: str
    role: str
    payload: object

    def __post_init__(self):
        if not isinstance(self.job_id, str) or not 0 < len(self.job_id) <= 80:
            raise ValueError("invalid job identifier")
        if not isinstance(self.role, str) or not self.role:
            raise ValueError("invalid agent role")


@dataclass(frozen=True)
class AgentResult:
    job_id: str
    role: str
    output: object
    elapsed_seconds: float


class BoundedParallelAgents:
    """Run trusted subagents concurrently; publish only complete successful batches."""

    def __init__(self, handlers, *, max_workers=4, max_jobs=16):
        if not isinstance(max_workers, int) or not 1 <= max_workers <= 8:
            raise ValueError("max_workers must be 1..8")
        if not isinstance(max_jobs, int) or not 1 <= max_jobs <= 64:
            raise ValueError("max_jobs must be 1..64")
        if not handlers or not all(isinstance(k, str) and k
                                   and callable(v) for k, v in handlers.items()):
            raise ValueError("trusted handler map required")
        self.handlers = MappingProxyType(dict(handlers))
        self.max_workers = max_workers
        self.max_jobs = max_jobs

    def run(self, jobs):
        jobs = tuple(jobs)
        if not 1 <= len(jobs) <= self.max_jobs:
            raise ValueError("batch exceeds allowed job count")
        if not all(isinstance(job, AgentJob) for job in jobs):
            raise TypeError("AgentJob required")
        if len({job.job_id for job in jobs}) != len(jobs):
            raise ValueError("duplicate job identifiers")
        if any(job.role not in self.handlers for job in jobs):
            raise ValueError("unregistered subagent role")

        def execute(job):
            started = perf_counter()
            result = self.handlers[job.role](job.payload)
            if result is None:
                raise ValueError("missing subagent output")
            return AgentResult(job.job_id, job.role, result,
                               perf_counter() - started)

        completed = {}
        errors = []
        with ThreadPoolExecutor(max_workers=self.max_workers,
                                thread_name_prefix="nerve-research") as pool:
            futures = {pool.submit(execute, job): job for job in jobs}
            for future in as_completed(futures):
                try:
                    outcome = future.result()
                except Exception as exc:
                    errors.append((futures[future].job_id, exc))
                else:
                    completed[outcome.job_id] = outcome

        # No partial batch result is returned on failure. The executor does
        # NOT forcibly terminate long-running code; no hard time limit exists.
        if errors:
            job_id, error = min(errors, key=lambda item: item[0])
            raise RuntimeError("subagent batch rejected: " + job_id) from error
        return tuple(completed[job.job_id] for job in jobs)
