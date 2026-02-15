def render_no_tasks() -> None:
    print("No tasks found. Run `python main.py seed` to populate the database.")


def render_tasks(tasks) -> None:
    for task in tasks:
        period_display = "-" if task.period is None else f"{task.period:.2f}"
        print(
            f"[{task.id}] {task.name} | r={task.release_time:.2f}, C={task.wcet:.2f}, "
            f"D={task.relative_deadline:.2f}, T={period_display}"
        )
