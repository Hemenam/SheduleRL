import unittest

from services.scheduler_service import ITBSJob, schedule_itbs


class TestSchedulerService(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
