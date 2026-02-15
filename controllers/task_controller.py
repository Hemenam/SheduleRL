from services import TaskService
from views import render_clear_complete, render_no_tasks, render_tasks


class TaskController:
    def __init__(self, task_service: TaskService):
        self.task_service = task_service

    def list(self) -> int:
        tasks = self.task_service.list_tasks()
        if not tasks:
            render_no_tasks()
            return 0

        render_tasks(tasks)
        return len(tasks)

    def clear(self) -> int:
        removed = self.task_service.delete_all_tasks()
        render_clear_complete(removed)
        return removed
