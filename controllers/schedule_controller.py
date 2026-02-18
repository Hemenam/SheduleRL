import random

from models.iot import EdgeServer, IoTDevice
from services import (
    ITBSJob,
    TaskService,
    generate_random_iot_workload,
    load_iot_simulation,
    schedule_iot_periodic_edf,
    schedule_iot_offloading_online,
    schedule_itbs,
)
from views import render_iot_schedule, render_schedule, save_gantt_plot, save_iot_gantt_plot


class ScheduleController:
    def __init__(self, task_service: TaskService):
        self.task_service = task_service

    def schedule(
        self,
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
            algorithm="itbs",
            bandwidths=selected_bandwidths,
        )

        if plot is not None:
            if plot != "gantt":
                raise ValueError(f"Unsupported plot type: {plot}")
            output = save_gantt_plot(
                results=results,
                task_name_by_id=task_name_by_id,
                output_path=plot_file,
                algorithm="itbs",
                bandwidths=selected_bandwidths,
            )
            print(f"Gantt plot saved to: {output}")

        return len(results)

    def schedule_offload(
        self,
        bandwidth: float = 0.5,
        bandwidths: list[float] | None = None,
        servers: int = 1,
        devices: int = 5,
        fixed_iot_count: bool = True,
        fixed_server_count: bool = True,
        simulation_horizon: float = 30.0,
        offline_period: float = 5.0,
        aperiodic_min_per_device: int = 1,
        aperiodic_max_per_device: int = 5,
        online_tick: float = 1.0,
        decision_budget: float = 0.01,
        random_seed: int | None = None,
        transfer_overhead: float = 0.0,
        reclaim_idle_time: bool = True,
        plot: str | None = None,
        plot_file: str = "offload_gantt.png",
        json_path: str | None = None,
    ) -> int:
        if json_path:
            devices, servers_list, iot_tasks, transfer_overhead, reclaim_idle_time = (
                load_iot_simulation(json_path)
            )
            offline_results = []
        else:
            rng = random.Random(random_seed)
            if devices < 1:
                raise ValueError("devices must be >= 1")
            if servers < 1:
                raise ValueError("servers must be >= 1")

            if bandwidths:
                selected_bandwidths = bandwidths
            else:
                server_count = servers if fixed_server_count else rng.randint(1, servers)
                selected_bandwidths = [bandwidth] * server_count

            device_count = devices if fixed_iot_count else rng.randint(1, devices)
            devices = [IoTDevice(device_id=i) for i in range(device_count)]
            servers_list = [
                EdgeServer(server_id=i, bandwidth=bw)
                for i, bw in enumerate(selected_bandwidths)
            ]
            periodic_tasks, iot_tasks = generate_random_iot_workload(
                devices=devices,
                simulation_horizon=simulation_horizon,
                offline_period=offline_period,
                aperiodic_min_per_device=aperiodic_min_per_device,
                aperiodic_max_per_device=aperiodic_max_per_device,
                seed=random_seed,
            )
            offline_results = schedule_iot_periodic_edf(
                tasks=periodic_tasks,
                devices=devices,
            )

        if offline_results:
            name_by_id = {task.task_id: task.name for task in periodic_tasks}
            render_schedule(
                results=offline_results,
                task_name_by_id=name_by_id,
                algorithm="edf-periodic-devices",
                bandwidths=None,
            )
            offline_plot_path = plot_file.replace(".png", "_offline.png")
            output = save_gantt_plot(
                results=offline_results,
                task_name_by_id=name_by_id,
                output_path=offline_plot_path,
                algorithm="edf-periodic-devices",
                bandwidths=None,
            )
            print(f"Offline periodic Gantt plot saved to: {output}")

        results = schedule_iot_offloading_online(
            tasks=iot_tasks,
            devices=devices,
            servers=servers_list,
            transfer_overhead=transfer_overhead,
            tick_interval=online_tick,
            decision_time=decision_budget,
            reclaim_idle_time=reclaim_idle_time,
        )

        render_iot_schedule(results=results)

        should_plot = plot is not None or json_path is None
        if should_plot:
            if plot != "gantt":
                if plot is not None:
                    raise ValueError(f"Unsupported plot type: {plot}")
            output = save_iot_gantt_plot(results=results, output_path=plot_file)
            print(f"Gantt plot saved to: {output}")

        return len(results)
