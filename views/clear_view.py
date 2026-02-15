from services import TaskService


def clear_tasks_view(task_service: TaskService) -> int:
    removed = task_service.delete_all_tasks()
    print(f"Clear complete: removed {removed} task(s).")
    return removed
