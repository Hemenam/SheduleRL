from typing import List

from sqlalchemy import select

from models.task import Task


class TaskService:
    def __init__(self, session):
        self.session = session

    def create_task(self, name: str, start: int, end: int, description: str | None = None) -> Task:
        task = Task(name=name, description=description, start=start, end=end)
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def list_tasks(self) -> List[Task]:
        statement = select(Task).order_by(Task.start.asc())
        return list(self.session.scalars(statement).all())

    def get_task(self, task_id: int) -> Task | None:
        return self.session.get(Task, task_id)

    def delete_task(self, task_id: int) -> bool:
        task = self.get_task(task_id)
        if not task:
            return False

        self.session.delete(task)
        self.session.commit()
        return True
