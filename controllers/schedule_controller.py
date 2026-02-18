from models.iot import EdgeServer, IoTDevice, IoTTask
from services import ITBSJob, TaskService, schedule_iot_offloading, schedule_itbs
from views import render_iot_schedule, render_schedule, save_gantt_plot, save_iot_gantt_plot


class ScheduleController:
    def __init__(self, task_service: TaskService):
        self.task_service = task_service

    def schedule(
        self,
        algorithm: str,
        bandwidth: float = 0.5,
        bandwidths: list[float] | None = None,
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

        selected_bandwidths = bandwidths if bandwidths else [bandwidth]

        results = schedule_itbs(
            jobs=jobs,
            server_bandwidths=selected_bandwidths,
            reclaim_idle_time=reclaim_idle_time,
        )

        render_schedule(
            results=results,
            task_name_by_id=task_name_by_id,
            algorithm=algorithm,
            bandwidths=selected_bandwidths,
        )

        if plot is not None:
            if plot != "gantt":
                raise ValueError(f"Unsupported plot type: {plot}")
            output = save_gantt_plot(
                results=results,
                task_name_by_id=task_name_by_id,
                output_path=plot_file,
                algorithm=algorithm,
                bandwidths=selected_bandwidths,
            )
            print(f"Gantt plot saved to: {output}")

        return len(results)

    def schedule_offload(
        self,
        bandwidth: float = 0.5,
        bandwidths: list[float] | None = None,
        servers: int = 1,
        transfer_overhead: float = 0.0,
        reclaim_idle_time: bool = True,
        plot: str | None = None,
        plot_file: str = "offload_gantt.png",
    ) -> int:
        tasks = self.task_service.list_tasks()
        if not tasks:
            print("No aperiodic tasks found. Run `python main.py seed` first.")
            return 0

        if bandwidths:
            selected_bandwidths = bandwidths
        else:
            if servers < 1:
                raise ValueError("servers must be >= 1")
            selected_bandwidths = [bandwidth] * servers

        devices = [IoTDevice(device_id=i) for i in range(len(tasks))]
        servers_list = [
            EdgeServer(server_id=i, bandwidth=bw)
            for i, bw in enumerate(selected_bandwidths)
        ]

        tasks_by_id = sorted(tasks, key=lambda task: task.id)
        iot_tasks: list[IoTTask] = []
        for idx, task in enumerate(tasks_by_id):
            iot_tasks.append(
                IoTTask(
                    task_id=str(task.id),
                    name=task.name,
                    release_time=float(task.release_time),
                    execution_time=float(task.wcet),
                    assigned_device_id=idx,
                )
            )

        results = schedule_iot_offloading(
            tasks=iot_tasks,
            devices=devices,
            servers=servers_list,
            transfer_overhead=transfer_overhead,
            reclaim_idle_time=reclaim_idle_time,
        )

        render_iot_schedule(results=results)

        if plot is not None:
            if plot != "gantt":
                raise ValueError(f"Unsupported plot type: {plot}")
            output = save_iot_gantt_plot(results=results, output_path=plot_file)
            print(f"Gantt plot saved to: {output}")

        return len(results)
