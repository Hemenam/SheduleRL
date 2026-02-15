from services import TaskService


DEFAULT_TASKS = [
    {
        "name": "Emergency Brake Audit",
        "release_time": 0.0,
        "wcet": 0.9,
        "relative_deadline": 1.8,
        "period": None,
        "description": "High-urgency diagnostic triggered at system startup.",
    },
    {
        "name": "Camera Frame Export",
        "release_time": 0.4,
        "wcet": 0.7,
        "relative_deadline": 2.4,
        "period": None,
        "description": "On-demand frame extraction for operator console.",
    },
    {
        "name": "Planner Reconfiguration",
        "release_time": 1.1,
        "wcet": 1.3,
        "relative_deadline": 3.2,
        "period": None,
        "description": "Runtime path-planner profile swap request.",
    },
    {
        "name": "Telemetry Burst Chunk 1",
        "release_time": 1.3,
        "wcet": 0.5,
        "relative_deadline": 2.2,
        "period": None,
        "description": "First packet in a burst upload sequence.",
    },
    {
        "name": "Telemetry Burst Chunk 2",
        "release_time": 1.45,
        "wcet": 0.6,
        "relative_deadline": 2.0,
        "period": None,
        "description": "Second packet in a burst upload sequence.",
    },
    {
        "name": "Telemetry Burst Chunk 3",
        "release_time": 1.6,
        "wcet": 0.55,
        "relative_deadline": 1.9,
        "period": None,
        "description": "Final packet in a burst upload sequence.",
    },
    {
        "name": "Lidar Map Snapshot",
        "release_time": 2.8,
        "wcet": 1.1,
        "relative_deadline": 3.0,
        "period": None,
        "description": "Aperiodic mapping request from remote supervisor.",
    },
    {
        "name": "Actuator Drift Check",
        "release_time": 3.4,
        "wcet": 0.8,
        "relative_deadline": 2.5,
        "period": None,
        "description": "Manual drift validation triggered after anomaly event.",
    },
    {
        "name": "Network Key Rotation",
        "release_time": 4.0,
        "wcet": 0.9,
        "relative_deadline": 3.5,
        "period": None,
        "description": "Security maintenance operation with bounded response.",
    },
    {
        "name": "Sensor Bias Refit",
        "release_time": 4.6,
        "wcet": 1.2,
        "relative_deadline": 3.1,
        "period": None,
        "description": "Post-impact calibration recovery routine.",
    },
    {
        "name": "UI Report Generation",
        "release_time": 5.1,
        "wcet": 1.0,
        "relative_deadline": 4.0,
        "period": None,
        "description": "Operator summary generation after mission segment.",
    },
    {
        "name": "Archive Compression",
        "release_time": 6.2,
        "wcet": 1.6,
        "relative_deadline": 5.0,
        "period": None,
        "description": "Background aperiodic archive packaging before uplink.",
    },
]


def seed_tasks_view(task_service: TaskService, force: bool = False) -> int:
    existing_tasks = task_service.list_tasks()
    if existing_tasks and not force:
        print("Seed skipped: tasks already exist. Use --force to append seed tasks.")
        return 0

    if force and existing_tasks:
        removed = task_service.delete_all_tasks()
        print(f"Seed reset: removed {removed} existing task(s).")

    created = 0
    for task in DEFAULT_TASKS:
        task_service.create_task(
            name=task["name"],
            release_time=task["release_time"],
            wcet=task["wcet"],
            relative_deadline=task["relative_deadline"],
            period=task["period"],
            description=task["description"],
        )
        created += 1

    print(f"Seed complete: created {created} task(s).")
    return created
