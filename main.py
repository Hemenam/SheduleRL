import argparse

from controllers import CommandController
from data import SessionLocal, init_db
from services import TaskService


def _parse_bandwidths(value: str) -> list[float]:
    parts = [part.strip() for part in value.split(",")]
    bandwidths = [float(part) for part in parts if part]
    if not bandwidths:
        raise argparse.ArgumentTypeError("Provide one or more comma-separated bandwidth values.")
    return bandwidths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ScheduRL real-time workload CLI")
    subparsers = parser.add_subparsers(dest="command")

    seed_parser = subparsers.add_parser("seed", help="Populate database with sample tasks")
    seed_parser.add_argument(
        "--force",
        action="store_true",
        help="Append seed tasks even when tasks already exist.",
    )

    subparsers.add_parser("list", help="List tasks")
    subparsers.add_parser("clear", help="Delete all tasks from the database")

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
        help="Single-server bandwidth U_s for iTBS in (0, 1].",
    )
    schedule_parser.add_argument(
        "--bandwidths",
        type=_parse_bandwidths,
        default=None,
        help="Comma-separated server bandwidths for multi-server iTBS (e.g. 0.4,0.6).",
    )
    schedule_parser.add_argument(
        "--no-reclaim",
        action="store_true",
        help="Disable iTBS idle-time reclaim behavior.",
    )
    schedule_parser.add_argument(
        "--plot",
        choices=["gantt"],
        default=None,
        help="Render schedule plot.",
    )
    schedule_parser.add_argument(
        "--plot-file",
        default="schedule_gantt.png",
        help="Output file path for plot image.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    init_db()

    with SessionLocal() as session:
        task_service = TaskService(session)
        controller = CommandController(task_service)
        controller.execute(args)


if __name__ == "__main__":
    main()
