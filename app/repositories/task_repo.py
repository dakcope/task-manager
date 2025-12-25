from typing import Optional
from uuid import UUID

from sqlalchemy import Select, select, update
from sqlalchemy.orm import Session

from app.core.enums import Priority, TaskStatus
from app.db.models.task import Task

class TaskRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, task: Task) -> Task:
        self._db.add(task)
        self._db.flush()
        return task

    def get(self, task_id: UUID) -> Optional[Task]:
        return self._db.get(Task, task_id)

    def list(
        self,
        *,
        limit: int,
        offset: int,
        status: Optional[TaskStatus] = None,
        priority: Optional[Priority] = None,
    ) -> list[Task]:
        stmt: Select = select(Task).order_by(Task.created_at.desc()).limit(limit).offset(offset)
        if status is not None:
            stmt = stmt.where(Task.status == status)
        if priority is not None:
            stmt = stmt.where(Task.priority == priority)
        return list(self._db.execute(stmt).scalars().all())

    def set_status(self, task_id: UUID, new_status: TaskStatus) -> int:
        stmt = (
            update(Task)
            .where(Task.id == task_id)
            .values(status=new_status)
        )
        res = self._db.execute(stmt)
        return res.rowcount or 0