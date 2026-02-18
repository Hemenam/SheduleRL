from argparse import Namespace

from services import TaskService

from controllers.schedule_controller import ScheduleController
from controllers.seed_controller import SeedController
from controllers.task_controller import TaskController


class CommandController:
    def __init__(self, task_service: TaskService):
        self.seed_controller = SeedController(task_service)
        self.task_controller = TaskController(task_service)
        self.schedule_controller = ScheduleController(task_service)

    def execute(self, args: Namespace) -> None:
        if args.command == "seed":
            self.seed_controller.seed(force=args.force)
            return

        if args.command == "schedule":
            self.schedule_controller.schedule(
                algorithm=args.algorithm,
                bandwidth=args.bandwidth,
                bandwidths=args.bandwidths,
                reclaim_idle_time=not args.no_reclaim,
                plot=args.plot,
                plot_file=args.plot_file,
            )
            return

        if args.command == "offload":
            self.schedule_controller.schedule_offload(
                bandwidth=args.bandwidth,
                bandwidths=args.bandwidths,
                servers=args.servers,
                transfer_overhead=args.transfer_overhead,
                reclaim_idle_time=not args.no_reclaim,
                plot=args.plot,
                plot_file=args.plot_file,
                json_path=args.json,
            )
            return

        if args.command == "clear":
            self.task_controller.clear()
            return

        self.task_controller.list()
