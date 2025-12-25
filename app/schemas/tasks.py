from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import Priority, TaskStatus


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=10_000)
    priority: Priority = Priority.MEDIUM


class TaskRead(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    priority: Priority
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    result: Optional[str]
    error: Optional[str]

    class Config:
        from_attributes = True


class TaskStatusRead(BaseModel):
    id: UUID
    status: TaskStatus

class TaskListRead(BaseModel):
    items: list[TaskRead]
    limit: int
    offset: int