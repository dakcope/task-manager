from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.enums import Priority, TaskStatus
from app.db.session import get_db
from app.schemas.tasks import TaskCreate, TaskListRead, TaskRead, TaskStatusRead
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["Задачи"])


def get_service(db: Session = Depends(get_db)) -> TaskService:
    return TaskService(db)


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED, summary="Создать задачу", description="Создание нновой задачи.")
def create_task(payload: TaskCreate, svc: TaskService = Depends(get_service)) -> TaskRead:
    task = svc.create_task(title=payload.title, description=payload.description, priority=payload.priority)
    return TaskRead.model_validate(task)


@router.get("/{task_id}", response_model=TaskRead, summary="Получить задачу", description="Получить всю информацию по задаче по её task_id.")
def get_task(task_id: UUID, svc: TaskService = Depends(get_service)) -> TaskRead:
    task = svc.get_task(task_id)
    return TaskRead.model_validate(task)


@router.get("", response_model=TaskListRead, summary="Список задач", description="Получить список задач.")
def list_tasks(
    limit: int = Query(20, ge=1, le=100, description="Количество задач в ответе"),
    offset: int = Query(0, ge=0, description="Смещение для пагинации"),
    status_filter: TaskStatus | None = Query(default=None, alias="status", description="Фильтр по статусу задачи"),
    priority_filter: Priority | None = Query(default=None, alias="priority", description="Фильтр по приоритету задачи"),
    svc: TaskService = Depends(get_service)) -> TaskListRead:
    items = svc.list_tasks(limit=limit, offset=offset, status=status_filter, priority=priority_filter)
    return TaskListRead(items=[TaskRead.model_validate(x) for x in items], limit=limit, offset=offset)


@router.get("/{task_id}/status", response_model=TaskStatusRead, summary="Статус задачи", description="Возвращает текущий статус задачи по её task_id.")
def get_task_status(task_id: UUID, svc: TaskService = Depends(get_service)) -> TaskStatusRead:
    task = svc.get_task(task_id)
    return TaskStatusRead(id=task.id, status=task.status)


@router.delete("/{task_id}", response_model=TaskRead, summary="Отменить задачу", description="Отменяет задачу, если она ещё не начала выполняться(IN_PROGRESS).")
def cancel_task(task_id: UUID, svc: TaskService = Depends(get_service)) -> TaskRead:
    task = svc.cancel_task(task_id)
    return TaskRead.model_validate(task)