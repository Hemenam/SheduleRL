import json
import tempfile
import unittest
from pathlib import Path

from models.iot import EdgeServer, IoTDevice, IoTTask
from services.iot_loader import generate_random_iot_workload, load_iot_simulation
from services.scheduler_service import schedule_iot_offloading, schedule_iot_offloading_online


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

    def test_load_periodic_tasks_expands_jobs(self) -> None:
        payload = {
            "transfer_overhead": 0.1,
            "simulation_horizon": 3.0,
            "jobs_per_device": 20,
            "servers": [{"server_id": 0, "bandwidth": 0.5}],
            "periodic_tasks": [
                {
                    "task_id": "dev0",
                    "name": "Periodic",
                    "release_offset": 0.0,
                    "period": 1.0,
                    "execution_time": 0.2,
                    "assigned_device_id": 0,
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "input.json"
            path.write_text(json.dumps(payload))
            devices, servers, tasks, overhead, reclaim = load_iot_simulation(str(path))

        self.assertEqual(overhead, 0.1)
        self.assertTrue(reclaim)
        self.assertEqual(len(devices), 1)
        self.assertEqual(len(servers), 1)
        self.assertEqual(len(tasks), 4)
        self.assertEqual([t.release_time for t in tasks], [0.0, 1.0, 2.0, 3.0])

    def test_generate_random_iot_workload_aperiodic_range(self) -> None:
        devices = [IoTDevice(device_id=0), IoTDevice(device_id=1)]
        periodic_tasks, online_tasks = generate_random_iot_workload(
            devices=devices,
            simulation_horizon=10.0,
            offline_period=5.0,
            aperiodic_min_per_device=1,
            aperiodic_max_per_device=5,
            seed=7,
        )

        self.assertGreaterEqual(len(periodic_tasks), 2)
        self.assertGreaterEqual(len(online_tasks), 2)
        counts_by_device = {0: 0, 1: 0}
        for task in online_tasks:
            counts_by_device[task.assigned_device_id] += 1
            self.assertGreaterEqual(task.release_time, 0.0)
            self.assertLessEqual(task.release_time, 10.0)
        self.assertGreaterEqual(counts_by_device[0], 1)
        self.assertLessEqual(counts_by_device[0], 5)
        self.assertGreaterEqual(counts_by_device[1], 1)
        self.assertLessEqual(counts_by_device[1], 5)

    def test_online_tick_scheduler_dispatches_every_tick(self) -> None:
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
                release_time=0.2,
                execution_time=1.0,
                assigned_device_id=0,
            ),
        ]

        results = schedule_iot_offloading_online(
            tasks=tasks,
            devices=devices,
            servers=servers,
            transfer_overhead=0.2,
            tick_interval=0.5,
            decision_time=0.01,
        )

        self.assertEqual(len(results), 2)
        self.assertFalse(results[0].was_offloaded)
        self.assertAlmostEqual(results[0].dispatch_time, 0.01, places=6)
        self.assertTrue(results[1].was_offloaded)
        self.assertAlmostEqual(results[1].dispatch_time, 0.51, places=6)
        self.assertAlmostEqual(results[1].decision_time, 0.01, places=6)


if __name__ == "__main__":
    unittest.main()
