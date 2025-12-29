import json
from dataclasses import dataclass
from uuid import uuid4

from app.core.enums import Priority, TaskStatus
from app.db.models.task import Task
from app.workers import consumer


class Ch:
    def __init__(self): self.published, self.acked = [], []
    def basic_publish(self, exchange, routing_key, body, properties=None): self.published.append((exchange, routing_key, body, properties))
    def basic_ack(self, delivery_tag): self.acked.append(delivery_tag)


@dataclass
class M:
    delivery_tag: int = 1
    routing_key: str = "tasks.high"


class P:
    def __init__(self, headers=None): self.headers = headers or {}


def body(task_id): return json.dumps({"task_id": str(task_id)}).encode()


def test_bad_json_dlq_ack(monkeypatch, db_session_factory):
    monkeypatch.setattr(consumer, "SessionLocal", db_session_factory)
    ch, m, p = Ch(), M(delivery_tag=10, routing_key="tasks.high"), P()
    consumer.on_message(ch, m, p, b"nope")
    assert ch.acked == [10] and len(ch.published) == 1 and ch.published[0][1] == "tasks.dlq" and ch.published[0][2] == b"nope"


def test_claim_fail_ack_no_change(monkeypatch, db_session_factory):
    monkeypatch.setattr(consumer, "SessionLocal", db_session_factory)
    tid = uuid4()
    s = db_session_factory(); s.add(Task(id=tid, title="t", description=None, priority=Priority.MEDIUM, status=TaskStatus.CANCELLED)); s.commit(); s.close()
    ch, m, p = Ch(), M(delivery_tag=1, routing_key="tasks.medium"), P()
    consumer.on_message(ch, m, p, body(tid))
    s2 = db_session_factory(); t = s2.get(Task, tid); s2.close()
    assert ch.acked == [1] and t.status == TaskStatus.CANCELLED


def test_success_completed(monkeypatch, db_session_factory):
    monkeypatch.setattr(consumer, "SessionLocal", db_session_factory)
    tid = uuid4()
    s = db_session_factory(); s.add(Task(id=tid, title="t", description=None, priority=Priority.HIGH, status=TaskStatus.PENDING)); s.commit(); s.close()
    monkeypatch.setattr(consumer, "_execute", lambda _: "OK")
    ch, m, p = Ch(), M(delivery_tag=7, routing_key="tasks.high"), P()
    consumer.on_message(ch, m, p, body(tid))
    s2 = db_session_factory(); t = s2.get(Task, tid); s2.close()
    assert ch.acked == [7] and t.status == TaskStatus.COMPLETED and t.started_at and t.finished_at and t.result == "OK" and t.error is None


def test_execute_error_failed(monkeypatch, db_session_factory):
    monkeypatch.setattr(consumer, "SessionLocal", db_session_factory)
    tid = uuid4()
    s = db_session_factory(); s.add(Task(id=tid, title="t", description=None, priority=Priority.LOW, status=TaskStatus.PENDING)); s.commit(); s.close()
    monkeypatch.setattr(consumer, "_execute", lambda _: (_ for _ in ()).throw(ValueError("boom")))
    ch, m, p = Ch(), M(delivery_tag=9, routing_key="tasks.low"), P()
    consumer.on_message(ch, m, p, body(tid))
    s2 = db_session_factory(); t = s2.get(Task, tid); s2.close()
    assert ch.acked == [9] and t.status == TaskStatus.FAILED and t.started_at and t.finished_at and t.error and "boom" in t.error


def test_outer_exception_republish_increments_retry(monkeypatch, db_session_factory):
    monkeypatch.setattr(consumer, "SessionLocal", db_session_factory)
    tid = uuid4()
    s = db_session_factory(); s.add(Task(id=tid, title="t", description=None, priority=Priority.HIGH, status=TaskStatus.PENDING)); s.commit(); s.close()
    monkeypatch.setattr(consumer, "_claim", lambda *_: (_ for _ in ()).throw(RuntimeError("db blew up")))
    ch, m, p = Ch(), M(delivery_tag=55, routing_key="tasks.high"), P(headers={"x-retry-count": 2})
    b = body(tid)
    consumer.on_message(ch, m, p, b)
    props = ch.published[0][3]
    assert ch.acked == [55] and len(ch.published) == 1 and ch.published[0][1] == "tasks.high" and props and props.headers["x-retry-count"] == 3


def test_outer_exception_dlq_when_retry_huge(monkeypatch, db_session_factory):
    monkeypatch.setattr(consumer, "SessionLocal", db_session_factory)
    tid = uuid4()
    s = db_session_factory(); s.add(Task(id=tid, title="t", description=None, priority=Priority.HIGH, status=TaskStatus.PENDING)); s.commit(); s.close()
    monkeypatch.setattr(consumer, "_claim", lambda *_: (_ for _ in ()).throw(RuntimeError("fail")))
    ch, m, p = Ch(), M(delivery_tag=77, routing_key="tasks.high"), P(headers={"x-retry-count": 9999})
    b = body(tid)
    consumer.on_message(ch, m, p, b)
    assert ch.acked == [77] and len(ch.published) == 1 and ch.published[0][1] == "tasks.dlq" and ch.published[0][2] == b