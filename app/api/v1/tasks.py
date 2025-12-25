from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.enums import Priority, TaskStatus
from app.db.session import get_db
from app.schemas.tasks import TaskCreate, TaskListRead, TaskRead, TaskStatusRead
from app.services.task_service import TaskService
from app.utils.exceptions import ConflictError, NotFoundError

router = APIRouter(prefix="/tasks", tags=["tasks"])


def get_service(db: Session = Depends(get_db)) -> TaskService:
    return TaskService(db)


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, svc: TaskService = Depends(get_service)) -> TaskRead:
    task = svc.create_task(title=payload.title, description=payload.description, priority=payload.priority)
    return TaskRead.model_validate(task)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: UUID, svc: TaskService = Depends(get_service)) -> TaskRead:
    try:
        task = svc.get_task(task_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return TaskRead.model_validate(task)


@router.get("", response_model=TaskListRead)
def list_tasks(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: Optional[TaskStatus] = Query(default=None, alias="status"),
    priority_filter: Optional[Priority] = Query(default=None, alias="priority"),
    svc: TaskService = Depends(get_service),
) -> TaskListRead:
    items = svc.list_tasks(limit=limit, offset=offset, status=status_filter, priority=priority_filter)
    return TaskListRead(
        items=[TaskRead.model_validate(x) for x in items],
        limit=limit,
        offset=offset,
    )


@router.get("/{task_id}/status", response_model=TaskStatusRead)
def get_task_status(task_id: UUID, svc: TaskService = Depends(get_service)) -> TaskStatusRead:
    try:
        task = svc.get_task(task_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return TaskStatusRead(id=task.id, status=task.status)


@router.delete("/{task_id}", response_model=TaskRead)
def cancel_task(task_id: UUID, svc: TaskService = Depends(get_service)) -> TaskRead:
    try:
        task = svc.cancel_task(task_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return TaskRead.model_validate(task)