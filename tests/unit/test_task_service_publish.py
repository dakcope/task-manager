import pytest

from app.core.enums import Priority, TaskStatus
from app.db.models.task import Task
from app.services.task_service import TaskService
from app.utils.exceptions import ExternalServiceError, ConflictError


def test_create_task_failed_if_rabbit_down(db_session, monkeypatch):
    monkeypatch.setattr("app.services.publisher.TaskPublisher.publish_task_created", lambda *_: (_ for _ in ()).throw(RuntimeError("Rabbit down")))
    with pytest.raises(ExternalServiceError):
        TaskService(db_session).create_task(title="t", description=None, priority=Priority.HIGH)
    t = db_session.query(Task).one()
    assert t.status == TaskStatus.FAILED and t.finished_at and t.error and "Rabbit down" in t.error


def test_create_task_pending_when_published(db_session, monkeypatch):
    calls = []
    monkeypatch.setattr("app.services.publisher.TaskPublisher.publish_task_created", lambda _, task_id, priority: calls.append((task_id, priority)))
    t = TaskService(db_session).create_task(title="t", description=None, priority=Priority.MEDIUM)
    assert t.id and t.status == TaskStatus.PENDING and calls == [(t.id, Priority.MEDIUM)]


def test_cancel_pending_sets_cancelled(db_session, monkeypatch):
    monkeypatch.setattr("app.services.publisher.TaskPublisher.publish_task_created", lambda *_: None)
    svc = TaskService(db_session)
    t = svc.create_task(title="t", description=None, priority=Priority.LOW)
    t2 = svc.cancel_task(t.id)
    assert t2.status == TaskStatus.CANCELLED and t2.finished_at


def test_cancel_completed_conflict(db_session):
    db_session.add(Task(title="done", description=None, priority=Priority.MEDIUM, status=TaskStatus.COMPLETED))
    db_session.commit()
    t = db_session.query(Task).one()
    with pytest.raises(ConflictError):
        TaskService(db_session).cancel_task(t.id)