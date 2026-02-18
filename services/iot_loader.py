import json
import random
from pathlib import Path

from models.iot import EdgeServer, IoTDevice, IoTTask


def _expand_periodic_tasks(
    periodic_tasks: list[dict],
    simulation_horizon: float,
    jobs_per_device: int,
) -> list[IoTTask]:
    if simulation_horizon < 0.0:
        raise ValueError("simulation_horizon must be >= 0.")
    if jobs_per_device < 1:
        raise ValueError("jobs_per_device must be >= 1.")

    tasks: list[IoTTask] = []
    for item in periodic_tasks:
        if not isinstance(item, dict):
            raise ValueError("Each periodic task entry must be an object.")
        device_id = int(item["assigned_device_id"])
        base_task_id = str(item.get("task_id", f"dev{device_id}"))
        name = str(item.get("name", base_task_id))
        release_offset = float(item.get("release_offset", 0.0))
        period = float(item["period"])
        execution_time = float(item["execution_time"])

        if period <= 0.0:
            raise ValueError("period must be > 0.")
        if execution_time <= 0.0:
            raise ValueError("execution_time must be > 0.")
        if release_offset < 0.0:
            raise ValueError("release_offset must be >= 0.")

        for job_index in range(jobs_per_device):
            release_time = release_offset + (job_index * period)
            if release_time > simulation_horizon:
                break
            task_id = f"{base_task_id}:{job_index}"
            tasks.append(
                IoTTask(
                    task_id=task_id,
                    name=name,
                    release_time=release_time,
                    execution_time=execution_time,
                    assigned_device_id=device_id,
                )
            )
    return tasks


def load_iot_simulation(
    json_path: str,
) -> tuple[list[IoTDevice], list[EdgeServer], list[IoTTask], float, bool]:
    path = Path(json_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")

    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("JSON root must be an object.")

    transfer_overhead = float(payload.get("transfer_overhead", 0.0))
    if transfer_overhead < 0.0:
        raise ValueError("transfer_overhead must be >= 0.")

    reclaim_idle_time = bool(payload.get("reclaim_idle_time", True))

    tasks: list[IoTTask] = []
    raw_tasks = payload.get("tasks")
    raw_periodic = payload.get("periodic_tasks")
    if raw_tasks is not None:
        if not isinstance(raw_tasks, list) or not raw_tasks:
            raise ValueError("If provided, 'tasks' must be a non-empty array.")
        for item in raw_tasks:
            if not isinstance(item, dict):
                raise ValueError("Each task entry must be an object.")
            task_id = str(item.get("task_id", item.get("id")))
            name = str(item.get("name", task_id))
            release_time = float(item["release_time"])
            execution_time = float(item["execution_time"])
            assigned_device_id = int(item["assigned_device_id"])
            tasks.append(
                IoTTask(
                    task_id=task_id,
                    name=name,
                    release_time=release_time,
                    execution_time=execution_time,
                    assigned_device_id=assigned_device_id,
                )
            )
    elif raw_periodic is not None:
        if not isinstance(raw_periodic, list) or not raw_periodic:
            raise ValueError("If provided, 'periodic_tasks' must be a non-empty array.")
        simulation_horizon = float(payload["simulation_horizon"])
        jobs_per_device = int(payload.get("jobs_per_device", 20))
        tasks = _expand_periodic_tasks(raw_periodic, simulation_horizon, jobs_per_device)
        if not tasks:
            raise ValueError("Periodic task expansion produced no tasks.")
    else:
        raise ValueError("JSON must include either 'tasks' or 'periodic_tasks'.")

    raw_devices = payload.get("devices")
    if raw_devices is None:
        device_ids = sorted({task.assigned_device_id for task in tasks})
        devices = [IoTDevice(device_id=device_id) for device_id in device_ids]
    else:
        if not isinstance(raw_devices, list) or not raw_devices:
            raise ValueError("If provided, 'devices' must be a non-empty array.")
        devices = []
        for item in raw_devices:
            if not isinstance(item, dict):
                raise ValueError("Each device entry must be an object.")
            device_id = int(item.get("device_id", item.get("id")))
            devices.append(IoTDevice(device_id=device_id))

    device_ids = {device.device_id for device in devices}
    for task in tasks:
        if task.assigned_device_id not in device_ids:
            raise ValueError(
                f"Task '{task.task_id}' assigned to unknown device {task.assigned_device_id}."
            )

    raw_servers = payload.get("servers")
    if not isinstance(raw_servers, list) or not raw_servers:
        raise ValueError("JSON must include a non-empty 'servers' array.")

    servers: list[EdgeServer] = []
    for index, item in enumerate(raw_servers):
        if not isinstance(item, dict):
            raise ValueError("Each server entry must be an object.")
        server_id = int(item.get("server_id", item.get("id", index)))
        bandwidth = float(item["bandwidth"])
        servers.append(EdgeServer(server_id=server_id, bandwidth=bandwidth))

    return devices, servers, tasks, transfer_overhead, reclaim_idle_time


def generate_random_iot_workload(
    devices: list[IoTDevice],
    simulation_horizon: float,
    offline_period: float = 5.0,
    aperiodic_min_per_device: int = 1,
    aperiodic_max_per_device: int = 5,
    seed: int | None = None,
) -> tuple[list[IoTTask], list[IoTTask]]:
    """
    Build a two-phase workload:
    - Offline phase: periodic jobs every `offline_period` seconds (with random offset/wcet).
    - Online phase: random number of aperiodic jobs per device.
    """
    if simulation_horizon <= 0.0:
        raise ValueError("simulation_horizon must be > 0.")
    if offline_period <= 0.0:
        raise ValueError("offline_period must be > 0.")
    if aperiodic_min_per_device < 1:
        raise ValueError("aperiodic_min_per_device must be >= 1.")
    if aperiodic_max_per_device < aperiodic_min_per_device:
        raise ValueError("aperiodic_max_per_device must be >= aperiodic_min_per_device.")

    rng = random.Random(seed)
    periodic_tasks: list[IoTTask] = []
    online_tasks: list[IoTTask] = []

    for device in devices:
        release_offset = rng.uniform(0.0, offline_period)
        job_index = 0
        release_time = release_offset
        while release_time <= simulation_horizon:
            periodic_tasks.append(
                IoTTask(
                    task_id=f"p{device.device_id}:{job_index}",
                    name=f"Periodic-{device.device_id}",
                    release_time=round(release_time, 3),
                    execution_time=round(rng.uniform(0.2, 1.2), 3),
                    assigned_device_id=device.device_id,
                )
            )
            job_index += 1
            release_time = release_offset + (job_index * offline_period)

        aperiodic_count = rng.randint(aperiodic_min_per_device, aperiodic_max_per_device)
        for task_index in range(aperiodic_count):
            online_tasks.append(
                IoTTask(
                    task_id=f"a{device.device_id}:{task_index}",
                    name=f"Aperiodic-{device.device_id}",
                    release_time=round(rng.uniform(0.0, simulation_horizon), 3),
                    execution_time=round(rng.uniform(0.2, 1.5), 3),
                    assigned_device_id=device.device_id,
                )
            )

    periodic_tasks.sort(key=lambda task: (task.release_time, task.task_id))
    online_tasks.sort(key=lambda task: (task.release_time, task.task_id))
    return periodic_tasks, online_tasks
