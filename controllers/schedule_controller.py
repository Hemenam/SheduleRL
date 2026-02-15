from services import ITBSJob, TaskService, schedule_itbs
from views import render_schedule, save_gantt_plot


class ScheduleController:
    def __init__(self, task_service: TaskService):
        self.task_service = task_service

    def schedule(
        self,
        algorithm: str,
        bandwidth: float = 0.5,
        reclaim_idle_time: bool = True,
        plot: str | None = None,
        plot_file: str = "schedule_gantt.png",
    ) -> int:
        tasks = self.task_service.list_tasks()
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

        render_schedule(
            results=results,
            task_name_by_id=task_name_by_id,
            algorithm=algorithm,
            bandwidth=bandwidth,
        )

        if plot is not None:
            if plot != "gantt":
                raise ValueError(f"Unsupported plot type: {plot}")
            output = save_gantt_plot(
                results=results,
                task_name_by_id=task_name_by_id,
                output_path=plot_file,
                algorithm=algorithm,
                bandwidth=bandwidth,
            )
            print(f"Gantt plot saved to: {output}")

        return len(results)
