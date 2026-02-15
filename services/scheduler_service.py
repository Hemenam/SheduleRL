from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ITBSJob:
    job_id: str
    arrival_time: float
    execution_time: float


@dataclass(frozen=True)
class ITBSScheduleResult:
    job_id: str
    arrival_time: float
    execution_time: float
    assigned_deadline: float
    service_start_time: float
    service_finish_time: float


def schedule_itbs(
    jobs: Iterable[ITBSJob],
    server_bandwidth: float,
    initial_deadline: float = 0.0,
    reclaim_idle_time: bool = True,
) -> list[ITBSScheduleResult]:
    """
    Compute iTBS deadlines for aperiodic jobs.

    iTBS assignment rule used:
    d_i = max(r_i, d_(i-1)) + (C_i / U_s)

    With `reclaim_idle_time=True`, the virtual server deadline is reset when the
    server has been idle, allowing the server to reclaim slack before the next job.
    """
    if server_bandwidth <= 0.0 or server_bandwidth > 1.0:
        raise ValueError("server_bandwidth must be in (0, 1].")

    sorted_jobs = sorted(jobs, key=lambda job: (job.arrival_time, job.job_id))
    results: list[ITBSScheduleResult] = []

    previous_virtual_deadline = float(initial_deadline)
    previous_finish_time = 0.0

    for job in sorted_jobs:
        if job.execution_time <= 0.0:
            raise ValueError(f"execution_time must be > 0 for job '{job.job_id}'.")

        if job.arrival_time < 0.0:
            raise ValueError(f"arrival_time must be >= 0 for job '{job.job_id}'.")

        if reclaim_idle_time and job.arrival_time > previous_finish_time:
            previous_virtual_deadline = max(initial_deadline, job.arrival_time)

        virtual_start = max(job.arrival_time, previous_virtual_deadline)
        assigned_deadline = virtual_start + (job.execution_time / server_bandwidth)

        service_start = max(job.arrival_time, previous_finish_time)
        service_finish = service_start + job.execution_time

        results.append(
            ITBSScheduleResult(
                job_id=job.job_id,
                arrival_time=job.arrival_time,
                execution_time=job.execution_time,
                assigned_deadline=assigned_deadline,
                service_start_time=service_start,
                service_finish_time=service_finish,
            )
        )

        previous_virtual_deadline = assigned_deadline
        previous_finish_time = service_finish

    return results
