from uuid import UUID

from sqlalchemy.orm import Session

from app.core.enums import Priority, TaskStatus
from app.db.models.task import Task
from app.repositories.task_repo import TaskRepository
from app.utils.exceptions import ConflictError, NotFoundError


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
        self._repo.create(task)
        self._db.commit()
        self._db.refresh(task)
        return task

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
        #TODO finished_at
        self._db.commit()
        self._db.refresh(task)
        return task