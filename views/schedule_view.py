from services import ITBSJob, TaskService, schedule_itbs


def schedule_view(
    task_service: TaskService,
    algorithm: str,
    bandwidth: float = 0.5,
    reclaim_idle_time: bool = True,
) -> int:
    tasks = task_service.list_tasks()
    if not tasks:
        print("No aperiodic tasks found. Run `python main.py seed` first.")
        return 0

    if algorithm != "itbs":
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    jobs: list[ITBSJob] = []
    task_name_by_id: dict[str, str] = {}

    for task in tasks:
        execution_time = float(task.wcet)
        if execution_time <= 0.0:
            raise ValueError(
                f"Task {task.id} ('{task.name}') has invalid wcet: must be > 0."
            )

        task_id = str(task.id)
        task_name_by_id[task_id] = task.name
        jobs.append(
            ITBSJob(
                job_id=task_id,
                arrival_time=float(task.release_time),
                execution_time=execution_time,
            )
        )

    results = schedule_itbs(
        jobs=jobs,
        server_bandwidth=bandwidth,
        reclaim_idle_time=reclaim_idle_time,
    )

    print(f"Schedule algorithm: {algorithm.upper()} (U_s={bandwidth:.3f})")
    for row in results:
        name = task_name_by_id[row.job_id]
        print(
            f"[{row.job_id}] {name} | "
            f"r={row.arrival_time:.2f}, C={row.execution_time:.2f}, "
            f"d={row.assigned_deadline:.2f}, "
            f"svc=[{row.service_start_time:.2f}, {row.service_finish_time:.2f}]"
        )

    return len(results)
