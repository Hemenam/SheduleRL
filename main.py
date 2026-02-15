from data import SessionLocal, init_db
from services import TaskService


def main() -> None:
    init_db()

    with SessionLocal() as session:
        task_service = TaskService(session)

        if not task_service.list_tasks():
            task_service.create_task(
                name="Prepare weekly schedule",
                description="Collect all course deadlines and lab sessions.",
                start=9,
                end=11,
            )

        for task in task_service.list_tasks():
            print(f"[{task.id}] {task.name} ({task.start}-{task.end})")


if __name__ == "__main__":
    main()
