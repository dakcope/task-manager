import pytest

from app.core.enums import Priority, TaskStatus
from app.services.task_service import TaskService
from app.utils.exceptions import ExternalServiceError


def test_create_task_rolls_back_if_rabbit_unavailable(db_session, monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("Rabbit down")

    monkeypatch.setattr("app.services.publisher.publish", _boom)

    svc = TaskService(db_session)

    with pytest.raises(ExternalServiceError):
        svc.create_task(title="t", description=None, priority=Priority.HIGH)


def test_create_task_sets_pending_when_published(db_session, monkeypatch):
    def _ok(*args, **kwargs):
        return None

    monkeypatch.setattr("app.services.publisher.publish", _ok)

    svc = TaskService(db_session)
    task = svc.create_task(title="t", description=None, priority=Priority.MEDIUM)

    assert task.status == TaskStatus.PENDING
    assert task.id is not None