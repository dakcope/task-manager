import pytest

from app.core.enums import Priority, TaskStatus
from app.db.models.task import Task
from app.services.task_service import TaskService
from app.utils.exceptions import ConflictError
from app.services.publisher import TaskPublisher
from app.db.models.outbox import OutboxEvent


def test_create_task_creates_outbox_event(db_session):
    svc = TaskService(db_session)
    t = svc.create_task(title="t", description=None, priority=Priority.HIGH)

    assert t.status == TaskStatus.PENDING
    assert db_session.query(Task).count() == 1

    e = db_session.query(OutboxEvent).one()
    rk, payload = TaskPublisher().build_task_created(t.id, Priority.HIGH)

    assert e.task_id == t.id
    assert e.routing_key == rk
    assert e.payload == payload


def test_cancel_pending_sets_cancelled(db_session):
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