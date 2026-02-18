from dataclasses import dataclass


@dataclass(frozen=True)
class IoTDevice:
    device_id: int


@dataclass(frozen=True)
class EdgeServer:
    server_id: int
    bandwidth: float


@dataclass(frozen=True)
class IoTTask:
    task_id: str
    name: str
    release_time: float
    execution_time: float
    assigned_device_id: int
