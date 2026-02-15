import argparse

from data import SessionLocal, init_db
from services import TaskService
from views import schedule_view, seed_tasks_view


def list_tasks_view(task_service: TaskService) -> None:
    tasks = task_service.list_tasks()
    if not tasks:
        print("No tasks found. Run `python main.py seed` to populate the database.")
        return

    for task in tasks:
        print(f"[{task.id}] {task.name} ({task.start}-{task.end})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ScheduRL task CLI")
    subparsers = parser.add_subparsers(dest="command")

    seed_parser = subparsers.add_parser("seed", help="Populate database with sample tasks")
    seed_parser.add_argument(
        "--force",
        action="store_true",
        help="Append seed tasks even when tasks already exist.",
    )

    subparsers.add_parser("list", help="List tasks")

    schedule_parser = subparsers.add_parser("schedule", help="Build a schedule from tasks")
    schedule_parser.add_argument(
        "-a",
        "--algorithm",
        required=True,
        choices=["itbs"],
        help="Scheduling algorithm to use.",
    )
    schedule_parser.add_argument(
        "-u",
        "--bandwidth",
        type=float,
        default=0.5,
        help="Server bandwidth U_s for iTBS in (0, 1].",
    )
    schedule_parser.add_argument(
        "--no-reclaim",
        action="store_true",
        help="Disable iTBS idle-time reclaim behavior.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    init_db()

    with SessionLocal() as session:
        task_service = TaskService(session)

        if args.command == "seed":
            seed_tasks_view(task_service, force=args.force)
            return

        if args.command == "schedule":
            schedule_view(
                task_service=task_service,
                algorithm=args.algorithm,
                bandwidth=args.bandwidth,
                reclaim_idle_time=not args.no_reclaim,
            )
            return

        list_tasks_view(task_service)


if __name__ == "__main__":
    main()
