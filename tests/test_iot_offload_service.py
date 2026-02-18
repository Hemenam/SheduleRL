import json
import tempfile
import unittest
from pathlib import Path

from models.iot import EdgeServer, IoTDevice, IoTTask
from services.iot_loader import load_iot_simulation
from services.scheduler_service import schedule_iot_offloading


class TestIoTOffloading(unittest.TestCase):
    def test_local_execution_when_device_idle(self) -> None:
        devices = [IoTDevice(device_id=0)]
        servers = [EdgeServer(server_id=0, bandwidth=0.5)]
        tasks = [
            IoTTask(
                task_id="a",
                name="A",
                release_time=0.0,
                execution_time=1.0,
                assigned_device_id=0,
            ),
            IoTTask(
                task_id="b",
                name="B",
                release_time=2.0,
                execution_time=1.0,
                assigned_device_id=0,
            ),
        ]

        results = schedule_iot_offloading(
            tasks=tasks,
            devices=devices,
            servers=servers,
            transfer_overhead=0.2,
        )

        self.assertEqual(len(results), 2)
        self.assertTrue(all(not row.was_offloaded for row in results))
        self.assertTrue(all(row.server_id == -1 for row in results))
        self.assertEqual(results[0].service_finish_time, 1.0)
        self.assertEqual(results[1].service_start_time, 2.0)

    def test_offload_when_device_busy(self) -> None:
        devices = [IoTDevice(device_id=0)]
        servers = [EdgeServer(server_id=0, bandwidth=0.5)]
        tasks = [
            IoTTask(
                task_id="a",
                name="A",
                release_time=0.0,
                execution_time=1.0,
                assigned_device_id=0,
            ),
            IoTTask(
                task_id="b",
                name="B",
                release_time=0.1,
                execution_time=1.0,
                assigned_device_id=0,
            ),
        ]

        results = schedule_iot_offloading(
            tasks=tasks,
            devices=devices,
            servers=servers,
            transfer_overhead=0.2,
        )

        self.assertEqual(len(results), 2)
        self.assertFalse(results[0].was_offloaded)
        self.assertTrue(results[1].was_offloaded)
        self.assertEqual(results[1].service_start_time, 0.1)
        self.assertAlmostEqual(results[1].service_finish_time, 1.3, places=6)
        self.assertAlmostEqual(results[1].assigned_deadline, 2.5, places=6)

    def test_load_iot_simulation_from_json(self) -> None:
        payload = {
            "transfer_overhead": 0.3,
            "reclaim_idle_time": False,
            "servers": [{"server_id": 0, "bandwidth": 0.5}],
            "tasks": [
                {
                    "task_id": "t1",
                    "name": "Job 1",
                    "release_time": 0.0,
                    "execution_time": 1.0,
                    "assigned_device_id": 0,
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "input.json"
            path.write_text(json.dumps(payload))
            devices, servers, tasks, overhead, reclaim = load_iot_simulation(str(path))

        self.assertEqual(overhead, 0.3)
        self.assertFalse(reclaim)
        self.assertEqual(len(devices), 1)
        self.assertEqual(len(servers), 1)
        self.assertEqual(len(tasks), 1)


if __name__ == "__main__":
    unittest.main()
