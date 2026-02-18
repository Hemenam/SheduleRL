import unittest

from services.scheduler_service import EDFJob, ITBSJob, schedule_edf, schedule_itbs


class TestSchedulerService(unittest.TestCase):
    def test_schedule_edf_orders_by_earliest_absolute_deadline(self) -> None:
        jobs = [
            EDFJob(job_id="a", arrival_time=0.0, execution_time=1.0, absolute_deadline=5.0),
            EDFJob(job_id="b", arrival_time=0.0, execution_time=1.0, absolute_deadline=3.0),
            EDFJob(job_id="c", arrival_time=2.0, execution_time=0.5, absolute_deadline=2.8),
        ]

        results = schedule_edf(jobs)

        self.assertEqual([r.job_id for r in results], ["b", "a", "c"])
        self.assertAlmostEqual(results[0].service_start_time, 0.0)
        self.assertAlmostEqual(results[1].service_start_time, 1.0)
        self.assertAlmostEqual(results[2].service_start_time, 2.0)
        self.assertAlmostEqual(results[2].assigned_deadline, 2.8)

    def test_schedule_edf_rejects_invalid_deadline(self) -> None:
        jobs = [
            EDFJob(job_id="x", arrival_time=1.0, execution_time=0.5, absolute_deadline=0.9),
        ]

        with self.assertRaises(ValueError):
            schedule_edf(jobs)

    def test_schedule_itbs_sorts_and_assigns_deadlines(self) -> None:
        jobs = [
            ITBSJob(job_id="b", arrival_time=1.0, execution_time=1.0),
            ITBSJob(job_id="a", arrival_time=0.0, execution_time=2.0),
        ]

        results = schedule_itbs(jobs, server_bandwidth=0.5)

        self.assertEqual([r.job_id for r in results], ["a", "b"])
        self.assertAlmostEqual(results[0].assigned_deadline, 4.0)
        self.assertAlmostEqual(results[1].assigned_deadline, 6.0)
        self.assertAlmostEqual(results[0].service_start_time, 0.0)
        self.assertAlmostEqual(results[1].service_start_time, 2.0)

    def test_schedule_itbs_reclaim_idle_time_changes_deadline(self) -> None:
        jobs = [
            ITBSJob(job_id="a", arrival_time=0.0, execution_time=2.0),
            ITBSJob(job_id="b", arrival_time=3.0, execution_time=1.0),
        ]

        with_reclaim = schedule_itbs(jobs, server_bandwidth=0.5, reclaim_idle_time=True)
        without_reclaim = schedule_itbs(jobs, server_bandwidth=0.5, reclaim_idle_time=False)

        self.assertAlmostEqual(with_reclaim[1].assigned_deadline, 5.0)
        self.assertAlmostEqual(without_reclaim[1].assigned_deadline, 6.0)

    def test_schedule_itbs_invalid_bandwidth_raises(self) -> None:
        jobs = [ITBSJob(job_id="x", arrival_time=0.0, execution_time=1.0)]

        with self.assertRaises(ValueError):
            schedule_itbs(jobs, server_bandwidth=0.0)

        with self.assertRaises(ValueError):
            schedule_itbs(jobs, server_bandwidth=1.1)

        with self.assertRaises(ValueError):
            schedule_itbs(jobs, server_bandwidths=[0.5, 1.2])

    def test_schedule_itbs_multiple_servers_assigns_earliest_available(self) -> None:
        jobs = [
            ITBSJob(job_id="a", arrival_time=0.0, execution_time=2.0),
            ITBSJob(job_id="b", arrival_time=0.0, execution_time=1.0),
            ITBSJob(job_id="c", arrival_time=1.0, execution_time=1.0),
        ]

        results = schedule_itbs(jobs, server_bandwidths=[0.5, 0.5])

        self.assertEqual([(r.job_id, r.server_id) for r in results], [("a", 0), ("b", 1), ("c", 1)])
        self.assertAlmostEqual(results[0].service_start_time, 0.0)
        self.assertAlmostEqual(results[1].service_start_time, 0.0)
        self.assertAlmostEqual(results[2].service_start_time, 1.0)


if __name__ == "__main__":
    unittest.main()
