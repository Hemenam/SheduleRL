from pydantic import BaseModel

class Task(BaseModel):
    name: str
    description: str | None
    start: int
    end: int
