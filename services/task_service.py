from typing import List

from sqlalchemy import delete, select

from models.task import RealTimeTask


class RealTimeTaskService:
    def __init__(self, session):
        self.session = session

    def create_task(
        self,
        name: str,
        release_time: float,
        wcet: float,
        relative_deadline: float,
        period: float | None = None,
        description: str | None = None,
    ) -> RealTimeTask:
        if wcet <= 0:
            raise ValueError("wcet must be > 0.")

        if relative_deadline <= 0:
            raise ValueError("relative_deadline must be > 0.")

        if period is not None and period <= 0:
            raise ValueError("period must be > 0 when provided.")

        task = RealTimeTask(
            name=name,
            task_type="aperiodic",
            release_time=release_time,
            wcet=wcet,
            relative_deadline=relative_deadline,
            period=period,
            description=description,
        )
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def list_tasks(self) -> List[RealTimeTask]:
        statement = select(RealTimeTask).order_by(
            RealTimeTask.release_time.asc(),
            RealTimeTask.id.asc(),
        )
        return list(self.session.scalars(statement).all())

    def list_aperiodic_tasks(self) -> List[RealTimeTask]:
        return self.list_tasks()

    def get_task(self, task_id: int) -> RealTimeTask | None:
        return self.session.get(RealTimeTask, task_id)

    def delete_task(self, task_id: int) -> bool:
        task = self.get_task(task_id)
        if not task:
            return False

        self.session.delete(task)
        self.session.commit()
        return True

    def delete_all_tasks(self) -> int:
        result = self.session.execute(delete(RealTimeTask))
        self.session.commit()
        return int(result.rowcount or 0)
