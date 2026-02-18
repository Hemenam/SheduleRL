import json
from pathlib import Path

from models.iot import EdgeServer, IoTDevice, IoTTask


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

    raw_tasks = payload.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise ValueError("JSON must include a non-empty 'tasks' array.")

    tasks: list[IoTTask] = []
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
