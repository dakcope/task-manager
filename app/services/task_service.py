import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import Priority, TaskStatus
from app.db.models.task import Task
from app.repositories.outbox_repo import OutboxRepository
from app.db.models.outbox import OutboxEvent
from app.repositories.task_repo import TaskRepository
from app.services.publisher import TaskPublisher
from app.utils.exceptions import ConflictError, NotFoundError

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class TaskService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = TaskRepository(db)
        self._outbox = OutboxRepository(db)

    def create_task(self, *, title: str, description: str | None, priority: Priority) -> Task:
        publisher = TaskPublisher()
        task = Task(title=title, description=description, priority=priority, status=TaskStatus.NEW)

        self._db.add(task)
        self._db.flush()

        task.status = TaskStatus.PENDING
        routing_key, payload = publisher.build_task_created(task.id, task.priority)
        self._outbox.add(OutboxEvent(task_id=task.id, routing_key=routing_key, payload=payload))
        self._db.commit()
        self._db.refresh(task)

        try:
            publisher.publish_task_created(task.id, task.priority)
        except Exception:
            logger.exception(f"Обработка задачи отложена. task_id={task.id}")

        return task

    def get_task(self, task_id: UUID) -> Task:
        task = self._repo.get(task_id)
        if task is None:
            raise NotFoundError(f"Задача task_id={task_id} не найдена.")
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
            raise ConflictError(f"Нельзя отменить задачу в статусе {task.status}. task_id={task_id}")

        task.status = TaskStatus.CANCELLED
        task.finished_at = utcnow()

        self._db.commit()
        self._db.refresh(task)
        return task