from services import TaskService


DEFAULT_TASKS = [
    {
        "name": "Control Loop Profiling",
        "description": "Measure WCET of control tasks on target hardware.",
        "start": 8,
        "end": 10,
    },
    {
        "name": "iTBS Server Simulation",
        "description": "Run aperiodic workload simulation and collect response times.",
        "start": 10,
        "end": 12,
    },
    {
        "name": "Deadline Miss Analysis",
        "description": "Inspect EDF timeline and identify overload windows.",
        "start": 13,
        "end": 15,
    },
    {
        "name": "Lab Integration",
        "description": "Integrate scheduler service with task ingestion flow.",
        "start": 16,
        "end": 18,
    },
]


def seed_tasks_view(task_service: TaskService, force: bool = False) -> int:
    existing_tasks = task_service.list_tasks()
    if existing_tasks and not force:
        print("Seed skipped: tasks already exist. Use --force to append seed tasks.")
        return 0

    created = 0
    for task in DEFAULT_TASKS:
        task_service.create_task(
            name=task["name"],
            description=task["description"],
            start=task["start"],
            end=task["end"],
        )
        created += 1

    print(f"Seed complete: created {created} task(s).")
    return created
