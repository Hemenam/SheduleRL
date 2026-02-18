import unittest

from models.iot import EdgeServer, IoTDevice, IoTTask
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


if __name__ == "__main__":
    unittest.main()
