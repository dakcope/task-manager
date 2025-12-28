from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import Priority, TaskStatus
from app.db.models.task import Task
from app.repositories.task_repo import TaskRepository
from app.services.publisher import TaskPublisher
from app.utils.exceptions import ConflictError, ExternalServiceError, NotFoundError


def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class TaskService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = TaskRepository(db)

    def create_task(self, *, title: str, description: str | None, priority: Priority) -> Task:
        task = Task(
            title=title,
            description=description,
            priority=priority,
            status=TaskStatus.NEW,
        )

        self._db.add(task)
        self._db.flush()

        task.status = TaskStatus.PENDING
        self._db.commit()
        self._db.refresh(task)

        try:
            TaskPublisher().publish_task_created(task.id, task.priority)
            return task

        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            task.finished_at = utcnow()
            self._db.commit()
            self._db.refresh(task)
            raise ExternalServiceError("RabbitMQ is unavailable") from exc

    def get_task(self, task_id: UUID) -> Task:
        task = self._repo.get(task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} not found")
        return task

    def list_tasks(
        self,
        *,
        limit: int,
        offset: int,
        status: TaskStatus | None,
        priority: Priority | None,
    ) -> list[Task]:
        return self._repo.list(limit=limit, offset=offset, status=status, priority=priority)

    def cancel_task(self, task_id: UUID) -> Task:
        task = self.get_task(task_id)

        if task.status not in (TaskStatus.NEW, TaskStatus.PENDING):
            raise ConflictError(f"Cannot cancel task in status {task.status}")

        task.status = TaskStatus.CANCELLED
        task.finished_at = utcnow()

        self._db.commit()
        self._db.refresh(task)
        return task