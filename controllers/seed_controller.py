from services import TaskService
from views import render_seed_complete, render_seed_reset, render_seed_skipped

from data.seed_data import DEFAULT_APERIODIC_TASKS


class SeedController:
    def __init__(self, task_service: TaskService):
        self.task_service = task_service

    def seed(self, force: bool = False) -> int:
        existing_tasks = self.task_service.list_tasks()
        if existing_tasks and not force:
            render_seed_skipped()
            return 0

        if force and existing_tasks:
            removed = self.task_service.delete_all_tasks()
            render_seed_reset(removed)

        created = 0
        for task in DEFAULT_APERIODIC_TASKS:
            self.task_service.create_task(
                name=task["name"],
                release_time=task["release_time"],
                wcet=task["wcet"],
                relative_deadline=task["relative_deadline"],
                period=task["period"],
                description=task["description"],
            )
            created += 1

        render_seed_complete(created)
        return created
