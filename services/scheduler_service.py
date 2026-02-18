from dataclasses import dataclass
from typing import Iterable

from models.iot import EdgeServer, IoTDevice, IoTTask


@dataclass(frozen=True)
class ITBSJob:
    job_id: str
    arrival_time: float
    execution_time: float


@dataclass(frozen=True)
class EDFJob:
    job_id: str
    arrival_time: float
    execution_time: float
    absolute_deadline: float


@dataclass(frozen=True)
class ITBSScheduleResult:
    job_id: str
    server_id: int
    server_bandwidth: float
    arrival_time: float
    execution_time: float
    assigned_deadline: float
    service_start_time: float
    service_finish_time: float


@dataclass(frozen=True)
class OffloadedJob:
    task_id: str
    task_name: str
    device_id: int
    server_id: int
    arrival_time: float
    execution_time: float
    assigned_deadline: float
    service_start_time: float
    service_finish_time: float
    transfer_overhead: float
    was_offloaded: bool
    dispatch_time: float = 0.0
    decision_time: float = 0.0


def schedule_edf(jobs: Iterable[EDFJob]) -> list[ITBSScheduleResult]:
    """
    Compute a non-preemptive single-processor EDF schedule for aperiodic jobs.
    """
    task_list = sorted(jobs, key=lambda job: (job.arrival_time, job.job_id))
    for job in task_list:
        if job.execution_time <= 0.0:
            raise ValueError(f"execution_time must be > 0 for job '{job.job_id}'.")
        if job.arrival_time < 0.0:
            raise ValueError(f"arrival_time must be >= 0 for job '{job.job_id}'.")
        if job.absolute_deadline < job.arrival_time:
            raise ValueError(
                f"absolute_deadline must be >= arrival_time for job '{job.job_id}'."
            )

    current_time = 0.0
    next_index = 0
    pending: list[EDFJob] = []
    results: list[ITBSScheduleResult] = []

    while next_index < len(task_list) or pending:
        while next_index < len(task_list) and task_list[next_index].arrival_time <= current_time:
            pending.append(task_list[next_index])
            next_index += 1

        if not pending:
            current_time = task_list[next_index].arrival_time
            continue

        selected_job_index = min(
            range(len(pending)),
            key=lambda idx: (
                pending[idx].absolute_deadline,
                pending[idx].arrival_time,
                pending[idx].job_id,
            ),
        )
        selected_job = pending.pop(selected_job_index)
        service_start = max(current_time, selected_job.arrival_time)
        service_finish = service_start + selected_job.execution_time
        current_time = service_finish

        results.append(
            ITBSScheduleResult(
                job_id=selected_job.job_id,
                server_id=0,
                server_bandwidth=1.0,
                arrival_time=selected_job.arrival_time,
                execution_time=selected_job.execution_time,
                assigned_deadline=selected_job.absolute_deadline,
                service_start_time=service_start,
                service_finish_time=service_finish,
            )
        )

    return results


def schedule_iot_periodic_edf(
    tasks: Iterable[IoTTask], devices: Iterable[IoTDevice]
) -> list[ITBSScheduleResult]:
    """
    Schedule periodic IoT jobs with per-device non-preemptive EDF.
    """
    device_list = list(devices)
    if not device_list:
        raise ValueError("At least one IoT device must be provided.")

    device_ids = {device.device_id for device in device_list}
    jobs_by_device: dict[int, list[EDFJob]] = {device.device_id: [] for device in device_list}

    for task in tasks:
        if task.execution_time <= 0.0:
            raise ValueError(f"execution_time must be > 0 for task '{task.task_id}'.")
        if task.release_time < 0.0:
            raise ValueError(f"release_time must be >= 0 for task '{task.task_id}'.")
        if task.assigned_device_id not in device_ids:
            raise ValueError(
                f"Task '{task.task_id}' assigned to unknown device {task.assigned_device_id}."
            )
        if task.relative_deadline is None or task.relative_deadline <= 0.0:
            raise ValueError(
                f"Periodic task '{task.task_id}' must provide relative_deadline > 0."
            )

        jobs_by_device[task.assigned_device_id].append(
            EDFJob(
                job_id=task.task_id,
                arrival_time=task.release_time,
                execution_time=task.execution_time,
                absolute_deadline=task.release_time + task.relative_deadline,
            )
        )

    results: list[ITBSScheduleResult] = []
    for device in device_list:
        device_results = schedule_edf(jobs_by_device[device.device_id])
        for result in device_results:
            results.append(
                ITBSScheduleResult(
                    job_id=result.job_id,
                    server_id=device.device_id,
                    server_bandwidth=1.0,
                    arrival_time=result.arrival_time,
                    execution_time=result.execution_time,
                    assigned_deadline=result.assigned_deadline,
                    service_start_time=result.service_start_time,
                    service_finish_time=result.service_finish_time,
                )
            )

    return sorted(
        results,
        key=lambda row: (row.service_start_time, row.server_id, row.job_id),
    )


def schedule_itbs(
    jobs: Iterable[ITBSJob],
    server_bandwidth: float | None = None,
    server_bandwidths: Iterable[float] | None = None,
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
    normalized_bandwidths: list[float] = []
    if server_bandwidths is not None:
        normalized_bandwidths = [float(value) for value in server_bandwidths]
    elif server_bandwidth is not None:
        normalized_bandwidths = [float(server_bandwidth)]

    if not normalized_bandwidths:
        raise ValueError("At least one server bandwidth must be provided.")

    for bw in normalized_bandwidths:
        if bw <= 0.0 or bw > 1.0:
            raise ValueError("Each server bandwidth must be in (0, 1].")

    sorted_jobs = sorted(jobs, key=lambda job: (job.arrival_time, job.job_id))
    results: list[ITBSScheduleResult] = []

    previous_virtual_deadlines = [float(initial_deadline)] * len(normalized_bandwidths)
    previous_finish_times = [0.0] * len(normalized_bandwidths)

    for job in sorted_jobs:
        if job.execution_time <= 0.0:
            raise ValueError(f"execution_time must be > 0 for job '{job.job_id}'.")

        if job.arrival_time < 0.0:
            raise ValueError(f"arrival_time must be >= 0 for job '{job.job_id}'.")

        selected_server_id = min(
            range(len(normalized_bandwidths)),
            key=lambda server_id: (
                max(job.arrival_time, previous_finish_times[server_id]),
                previous_virtual_deadlines[server_id],
                server_id,
            ),
        )
        selected_bandwidth = normalized_bandwidths[selected_server_id]
        previous_virtual_deadline = previous_virtual_deadlines[selected_server_id]
        previous_finish_time = previous_finish_times[selected_server_id]

        if reclaim_idle_time and job.arrival_time > previous_finish_time:
            previous_virtual_deadline = max(initial_deadline, job.arrival_time)

        virtual_start = max(job.arrival_time, previous_virtual_deadline)
        assigned_deadline = virtual_start + (job.execution_time / selected_bandwidth)

        service_start = max(job.arrival_time, previous_finish_time)
        service_finish = service_start + job.execution_time

        results.append(
            ITBSScheduleResult(
                job_id=job.job_id,
                server_id=selected_server_id,
                server_bandwidth=selected_bandwidth,
                arrival_time=job.arrival_time,
                execution_time=job.execution_time,
                assigned_deadline=assigned_deadline,
                service_start_time=service_start,
                service_finish_time=service_finish,
            )
        )

        previous_virtual_deadlines[selected_server_id] = assigned_deadline
        previous_finish_times[selected_server_id] = service_finish

    return results


def schedule_iot_offloading(
    tasks: Iterable[IoTTask],
    devices: Iterable[IoTDevice],
    servers: Iterable[EdgeServer],
    transfer_overhead: float,
    reclaim_idle_time: bool = True,
) -> list[OffloadedJob]:
    """
    Schedule IoT tasks with online offloading.

    Model assumptions:
    - There are n tasks and n IoT devices; each task is initially assigned to one device.
    - A task executes on its assigned IoT device if the device is idle at arrival.
    - If the device is busy at arrival, the task is offloaded to one of k servers.
    - Offloading incurs a constant transfer overhead `t` added to the task service time.
    - Servers use iTBS to assign deadlines and schedule service.
    """
    device_list = list(devices)
    server_list = list(servers)
    task_list = sorted(
        tasks, key=lambda task: (task.release_time, task.task_id)
    )

    if not device_list:
        raise ValueError("At least one IoT device must be provided.")
    if not server_list:
        raise ValueError("At least one server must be provided.")
    if transfer_overhead < 0.0:
        raise ValueError("transfer_overhead must be >= 0.")

    device_ids = {device.device_id for device in device_list}
    server_bandwidths = [server.bandwidth for server in server_list]
    for bw in server_bandwidths:
        if bw <= 0.0 or bw > 1.0:
            raise ValueError("Each server bandwidth must be in (0, 1].")

    device_finish_times = {device.device_id: 0.0 for device in device_list}
    server_virtual_deadlines = [0.0] * len(server_list)
    server_finish_times = [0.0] * len(server_list)

    results: list[OffloadedJob] = []

    for task in task_list:
        if task.execution_time <= 0.0:
            raise ValueError(f"execution_time must be > 0 for task '{task.task_id}'.")
        if task.release_time < 0.0:
            raise ValueError(f"release_time must be >= 0 for task '{task.task_id}'.")
        if task.assigned_device_id not in device_ids:
            raise ValueError(
                f"Task '{task.task_id}' assigned to unknown device {task.assigned_device_id}."
            )

        device_available = device_finish_times[task.assigned_device_id]

        if task.release_time >= device_available:
            service_start = task.release_time
            service_finish = service_start + task.execution_time
            device_finish_times[task.assigned_device_id] = service_finish
            results.append(
                OffloadedJob(
                    task_id=task.task_id,
                    task_name=task.name,
                    device_id=task.assigned_device_id,
                    server_id=-1,
                    arrival_time=task.release_time,
                    execution_time=task.execution_time,
                    assigned_deadline=service_finish,
                    service_start_time=service_start,
                    service_finish_time=service_finish,
                    transfer_overhead=0.0,
                    was_offloaded=False,
                )
            )
            continue

        selected_server_id = min(
            range(len(server_list)),
            key=lambda server_id: (
                max(task.release_time, server_finish_times[server_id]),
                server_virtual_deadlines[server_id],
                server_id,
            ),
        )
        server_bw = server_bandwidths[selected_server_id]
        prev_deadline = server_virtual_deadlines[selected_server_id]
        prev_finish = server_finish_times[selected_server_id]

        if reclaim_idle_time and task.release_time > prev_finish:
            prev_deadline = max(0.0, task.release_time)

        virtual_start = max(task.release_time, prev_deadline)
        effective_execution = task.execution_time + transfer_overhead
        assigned_deadline = virtual_start + (effective_execution / server_bw)

        service_start = max(task.release_time, prev_finish)
        service_finish = service_start + effective_execution

        server_virtual_deadlines[selected_server_id] = assigned_deadline
        server_finish_times[selected_server_id] = service_finish

        results.append(
            OffloadedJob(
                task_id=task.task_id,
                task_name=task.name,
                device_id=task.assigned_device_id,
                server_id=selected_server_id,
                arrival_time=task.release_time,
                execution_time=task.execution_time,
                assigned_deadline=assigned_deadline,
                service_start_time=service_start,
                service_finish_time=service_finish,
                transfer_overhead=transfer_overhead,
                was_offloaded=True,
            )
        )

    return results


def schedule_iot_offloading_online(
    tasks: Iterable[IoTTask],
    devices: Iterable[IoTDevice],
    servers: Iterable[EdgeServer],
    transfer_overhead: float,
    tick_interval: float = 1.0,
    decision_time: float = 0.01,
    reclaim_idle_time: bool = True,
) -> list[OffloadedJob]:
    """
    Online, procedure-based scheduling:
    - A dispatcher procedure runs once every `tick_interval` seconds.
    - At each tick, dispatch decisions are completed within `decision_time`.
    """
    if tick_interval <= 0.0:
        raise ValueError("tick_interval must be > 0.")
    if decision_time < 0.0:
        raise ValueError("decision_time must be >= 0.")
    if decision_time >= tick_interval:
        raise ValueError("decision_time must be smaller than tick_interval.")

    device_list = list(devices)
    server_list = list(servers)
    task_list = sorted(tasks, key=lambda task: (task.release_time, task.task_id))

    if not device_list:
        raise ValueError("At least one IoT device must be provided.")
    if not server_list:
        raise ValueError("At least one server must be provided.")
    if transfer_overhead < 0.0:
        raise ValueError("transfer_overhead must be >= 0.")

    device_ids = {device.device_id for device in device_list}
    server_bandwidths = [server.bandwidth for server in server_list]
    for bw in server_bandwidths:
        if bw <= 0.0 or bw > 1.0:
            raise ValueError("Each server bandwidth must be in (0, 1].")

    pending_by_device: dict[int, list[IoTTask]] = {device_id: [] for device_id in device_ids}
    device_finish_times = {device.device_id: 0.0 for device in device_list}
    server_virtual_deadlines = [0.0] * len(server_list)
    server_finish_times = [0.0] * len(server_list)
    results: list[OffloadedJob] = []

    next_task_index = 0
    tick = 0.0
    final_arrival = task_list[-1].release_time if task_list else 0.0

    while next_task_index < len(task_list) or any(pending_by_device.values()):
        while (
            next_task_index < len(task_list)
            and task_list[next_task_index].release_time <= tick + 1e-9
        ):
            task = task_list[next_task_index]
            if task.execution_time <= 0.0:
                raise ValueError(f"execution_time must be > 0 for task '{task.task_id}'.")
            if task.release_time < 0.0:
                raise ValueError(f"release_time must be >= 0 for task '{task.task_id}'.")
            if task.assigned_device_id not in device_ids:
                raise ValueError(
                    f"Task '{task.task_id}' assigned to unknown device {task.assigned_device_id}."
                )
            pending_by_device[task.assigned_device_id].append(task)
            next_task_index += 1

        dispatch_time = tick + decision_time
        for device_id in sorted(pending_by_device.keys()):
            queue = pending_by_device[device_id]
            if not queue:
                continue
            task = queue.pop(0)

            device_available = device_finish_times[task.assigned_device_id]
            if dispatch_time >= device_available:
                service_start = max(dispatch_time, task.release_time)
                service_finish = service_start + task.execution_time
                device_finish_times[task.assigned_device_id] = service_finish
                results.append(
                    OffloadedJob(
                        task_id=task.task_id,
                        task_name=task.name,
                        device_id=task.assigned_device_id,
                        server_id=-1,
                        arrival_time=task.release_time,
                        execution_time=task.execution_time,
                        assigned_deadline=service_finish,
                        service_start_time=service_start,
                        service_finish_time=service_finish,
                        transfer_overhead=0.0,
                        was_offloaded=False,
                        dispatch_time=dispatch_time,
                        decision_time=decision_time,
                    )
                )
                continue

            selected_server_id = min(
                range(len(server_list)),
                key=lambda server_id: (
                    max(dispatch_time, server_finish_times[server_id]),
                    server_virtual_deadlines[server_id],
                    server_id,
                ),
            )
            server_bw = server_bandwidths[selected_server_id]
            prev_deadline = server_virtual_deadlines[selected_server_id]
            prev_finish = server_finish_times[selected_server_id]

            if reclaim_idle_time and dispatch_time > prev_finish:
                prev_deadline = max(0.0, dispatch_time)

            virtual_start = max(dispatch_time, prev_deadline)
            effective_execution = task.execution_time + transfer_overhead
            assigned_deadline = virtual_start + (effective_execution / server_bw)

            service_start = max(dispatch_time, prev_finish)
            service_finish = service_start + effective_execution

            server_virtual_deadlines[selected_server_id] = assigned_deadline
            server_finish_times[selected_server_id] = service_finish

            results.append(
                OffloadedJob(
                    task_id=task.task_id,
                    task_name=task.name,
                    device_id=task.assigned_device_id,
                    server_id=selected_server_id,
                    arrival_time=task.release_time,
                    execution_time=task.execution_time,
                    assigned_deadline=assigned_deadline,
                    service_start_time=service_start,
                    service_finish_time=service_finish,
                    transfer_overhead=transfer_overhead,
                    was_offloaded=True,
                    dispatch_time=dispatch_time,
                    decision_time=decision_time,
                )
            )

        if next_task_index < len(task_list) or any(pending_by_device.values()):
            tick += tick_interval
        elif tick < final_arrival:
            tick = final_arrival

    return results
