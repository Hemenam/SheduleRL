import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from controllers.schedule_controller import ScheduleController
from controllers.seed_controller import SeedController
from controllers.task_controller import TaskController
from data.database import Base
from services.task_service import RealTimeTaskService


class DatabaseBackedTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        db_path = Path(self.tempdir.name) / "test_tasks.db"
        self.engine = create_engine(f"sqlite:///{db_path}", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            future=True,
        )
        self.session = self.SessionLocal()
        self.task_service = RealTimeTaskService(self.session)

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()
        self.tempdir.cleanup()

    def create_task(
        self, name: str, release: float, wcet: float = 1.0, deadline: float | None = None
    ) -> None:
        self.task_service.create_task(
            name=name,
            release_time=release,
            wcet=wcet,
            relative_deadline=deadline if deadline is not None else wcet + 1.0,
            period=None,
            description=f"{name} description",
        )


class TestTaskService(DatabaseBackedTestCase):
    def test_create_and_list_sorted_by_release_time(self) -> None:
        self.create_task("late", release=10.0)
        self.create_task("early", release=1.0)

        tasks = self.task_service.list_tasks()

        self.assertEqual([t.name for t in tasks], ["early", "late"])
        self.assertTrue(all(t.task_type == "aperiodic" for t in tasks))

    def test_delete_all_tasks_returns_count(self) -> None:
        self.create_task("a", release=0.0)
        self.create_task("b", release=2.0)

        removed = self.task_service.delete_all_tasks()

        self.assertEqual(removed, 2)
        self.assertEqual(len(self.task_service.list_tasks()), 0)


class TestSeedController(DatabaseBackedTestCase):
    def test_seed_controller_seed_and_force(self) -> None:
        seed_payload = [
            {
                "name": "s1",
                "release_time": 0.0,
                "wcet": 1.0,
                "relative_deadline": 2.0,
                "period": None,
                "description": "s1",
            },
            {
                "name": "s2",
                "release_time": 1.0,
                "wcet": 0.5,
                "relative_deadline": 1.5,
                "period": None,
                "description": "s2",
            },
        ]

        controller = SeedController(self.task_service)

        with patch("controllers.seed_controller.DEFAULT_APERIODIC_TASKS", seed_payload), patch(
            "controllers.seed_controller.render_seed_complete"
        ) as mock_complete, patch(
            "controllers.seed_controller.render_seed_skipped"
        ) as mock_skipped, patch(
            "controllers.seed_controller.render_seed_reset"
        ) as mock_reset:
            created = controller.seed(force=False)
            self.assertEqual(created, 2)
            mock_complete.assert_called_with(2)
            mock_skipped.assert_not_called()
            mock_reset.assert_not_called()

            skipped = controller.seed(force=False)
            self.assertEqual(skipped, 0)
            mock_skipped.assert_called_once()

            created_force = controller.seed(force=True)
            self.assertEqual(created_force, 2)
            mock_reset.assert_called_once_with(2)


class TestTaskController(DatabaseBackedTestCase):
    def test_list_empty_and_non_empty_and_clear(self) -> None:
        controller = TaskController(self.task_service)

        with patch("controllers.task_controller.render_no_tasks") as mock_no_tasks, patch(
            "controllers.task_controller.render_tasks"
        ) as mock_render_tasks, patch(
            "controllers.task_controller.render_clear_complete"
        ) as mock_clear:
            count_empty = controller.list()
            self.assertEqual(count_empty, 0)
            mock_no_tasks.assert_called_once()

            self.create_task("run", release=1.0)

            count_non_empty = controller.list()
            self.assertEqual(count_non_empty, 1)
            self.assertEqual(mock_render_tasks.call_count, 1)

            removed = controller.clear()
            self.assertEqual(removed, 1)
            mock_clear.assert_called_once_with(1)


class TestScheduleController(DatabaseBackedTestCase):
    def test_schedule_calls_render_and_plot(self) -> None:
        self.create_task("j1", release=0.0, wcet=1.0)
        self.create_task("j2", release=1.0, wcet=0.5)
        controller = ScheduleController(self.task_service)

        with patch("controllers.schedule_controller.render_schedule") as mock_render, patch(
            "controllers.schedule_controller.save_gantt_plot",
            return_value=Path("/tmp/test.png"),
        ) as mock_plot, patch("builtins.print") as mock_print:
            count = controller.schedule(
                bandwidth=0.5,
                reclaim_idle_time=True,
                plot="gantt",
                plot_file="out.png",
            )

            self.assertEqual(count, 2)
            mock_render.assert_called_once()
            mock_plot.assert_called_once()
            mock_print.assert_called_once()

    def test_schedule_no_tasks_returns_zero(self) -> None:
        controller = ScheduleController(self.task_service)
        with patch("builtins.print") as mock_print:
            count = controller.schedule()
            self.assertEqual(count, 0)
            mock_print.assert_called_once()


if __name__ == "__main__":
    unittest.main()
