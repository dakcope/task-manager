from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from app.core.enums import Priority, TaskStatus


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10_000)
    priority: Priority = Priority.MEDIUM


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    priority: Priority
    status: TaskStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    result: str | None
    error: str | None


class TaskStatusRead(BaseModel):
    id: UUID
    status: TaskStatus

class TaskListRead(BaseModel):
    items: list[TaskRead]
    limit: int
    offset: int