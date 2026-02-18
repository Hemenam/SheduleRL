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

    offload_parser = subparsers.add_parser(
        "offload", help="Schedule IoT tasks with online edge offloading"
    )
    offload_parser.add_argument(
        "-u",
        "--bandwidth",
        type=float,
        default=0.5,
        help="Single-server bandwidth U_s for offloading in (0, 1].",
    )
    offload_parser.add_argument(
        "--bandwidths",
        type=_parse_bandwidths,
        default=None,
        help="Comma-separated server bandwidths for multi-server mode (example: 0.4,0.6).",
    )
    offload_parser.add_argument(
        "-k",
        "--servers",
        type=int,
        default=1,
        help="Number of identical servers if --bandwidths is not provided.",
    )
    offload_parser.add_argument(
        "-t",
        "--transfer-overhead",
        type=float,
        default=0.0,
        help="Constant offloading overhead added to each offloaded task.",
    )
    offload_parser.add_argument(
        "--json",
        default=None,
        help="Path to JSON input describing devices, servers, tasks, and overhead.",
    )
    offload_parser.add_argument(
        "--no-reclaim",
        action="store_true",
        help="Disable iTBS idle-time reclaim behavior on servers.",
    )
    offload_parser.add_argument(
        "--plot",
        choices=["gantt"],
        default="gantt",
        help="Render schedule plot.",
    )
    offload_parser.add_argument(
        "--plot-file",
        default="offload_gantt.png",
        help="Output file path for plot image.",
    )
    offload_parser.add_argument(
        "--devices",
        type=int,
        default=5,
        help="Maximum or fixed number of IoT devices (based on --fixed-iot-count).",
    )
    offload_parser.add_argument(
        "--fixed-iot-count",
        action="store_true",
        help="Use exactly --devices (otherwise device count is random in [1, --devices]).",
    )
    offload_parser.add_argument(
        "--fixed-server-count",
        action="store_true",
        help="Use exactly --servers (otherwise server count is random in [1, --servers]).",
    )
    offload_parser.add_argument(
        "--horizon",
        type=float,
        default=30.0,
        help="Simulation horizon for random offline/online workload generation.",
    )
    offload_parser.add_argument(
        "--offline-period",
        type=float,
        default=5.0,
        help="Offline periodic release period in seconds.",
    )
    offload_parser.add_argument(
        "--aperiodic-min-per-device",
        type=int,
        default=1,
        help="Minimum random aperiodic tasks per device in online phase.",
    )
    offload_parser.add_argument(
        "--aperiodic-max-per-device",
        type=int,
        default=5,
        help="Maximum random aperiodic tasks per device in online phase.",
    )
    offload_parser.add_argument(
        "--online-tick",
        type=float,
        default=1.0,
        help="Online scheduler procedure interval in seconds.",
    )
    offload_parser.add_argument(
        "--decision-budget",
        type=float,
        default=0.01,
        help="Decision time budget per procedure tick in seconds.",
    )
    offload_parser.add_argument(
        "--random-seed",
        type=int,
        default=None,
        help="Optional random seed for reproducible workload generation.",
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
