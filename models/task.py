from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from data.database import Base


class RealTimeTask(Base):
    __tablename__ = "real_time_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    task_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        default="aperiodic",
    )
    release_time: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    wcet: Mapped[float] = mapped_column(Float, nullable=False)
    relative_deadline: Mapped[float] = mapped_column(Float, nullable=False)
    period: Mapped[float] = mapped_column(Float, nullable=True)
    description: Mapped[str] = mapped_column(String(500), nullable=True)
