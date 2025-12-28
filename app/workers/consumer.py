import json
from datetime import datetime, timezone
from uuid import UUID

import pika
from sqlalchemy import update

from app.core.config import settings
from app.core.enums import TaskStatus
from app.db.models.task import Task
from app.db.session import SessionLocal


def _now():
    return datetime.now(timezone.utc)


def _declare(channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
    for q in (settings.TASKS_QUEUE_HIGH, settings.TASKS_QUEUE_MEDIUM, settings.TASKS_QUEUE_LOW, "tasks.dlq"):
        channel.queue_declare(queue=q, durable=True)


def _retry_count(props: pika.BasicProperties) -> int:
    v = (props.headers or {}).get("x-retry-count", 0)
    try:
        return int(v)
    except Exception:
        return 0


def _republish(channel, routing_key: str, body: bytes, props: pika.BasicProperties, retry_count: int) -> None:
    headers = dict(props.headers or {})
    headers["x-retry-count"] = retry_count
    channel.basic_publish(
        exchange="",
        routing_key=routing_key,
        body=body,
        properties=pika.BasicProperties(content_type="application/json", delivery_mode=2, headers=headers),
    )


def _publish_dlq(channel, body: bytes, props: pika.BasicProperties) -> None:
    channel.basic_publish(
        exchange="",
        routing_key="tasks.dlq",
        body=body,
        properties=pika.BasicProperties(
            content_type="application/json",
            delivery_mode=2,
            headers=dict(props.headers or {}),
        ),
    )


def _parse(body: bytes) -> UUID:
    data = json.loads(body.decode("utf-8"))
    return UUID(str(data["task_id"]))


def _claim(db, task_id: UUID) -> bool:
    res = db.execute(
        update(Task)
        .where(Task.id == task_id, Task.status == TaskStatus.PENDING)
        .values(status=TaskStatus.IN_PROGRESS, started_at=_now())
    )
    return (res.rowcount or 0) == 1


def _complete(db, task_id: UUID, result: str) -> None:
    db.execute(
        update(Task)
        .where(Task.id == task_id)
        .values(status=TaskStatus.COMPLETED, result=result, error=None, finished_at=_now())
    )


def _fail(db, task_id: UUID, error: str) -> None:
    db.execute(
        update(Task)
        .where(Task.id == task_id)
        .values(status=TaskStatus.FAILED, error=error, finished_at=_now())
    )


def _execute(task_id: UUID) -> str:
    return f"ok:{task_id}"


def on_message(channel, method, props: pika.BasicProperties, body: bytes) -> None:
    try:
        task_id = _parse(body)
    except Exception:
        _publish_dlq(channel, body, props)
        channel.basic_ack(method.delivery_tag)
        return

    db = SessionLocal()
    try:
        if not _claim(db, task_id):
            db.commit()
            channel.basic_ack(method.delivery_tag)
            return

        try:
            result = _execute(task_id)
            _complete(db, task_id, result)
            db.commit()
            channel.basic_ack(method.delivery_tag)
            return
        except Exception as e:
            _fail(db, task_id, str(e))
            db.commit()
            channel.basic_ack(method.delivery_tag)
            return

    except Exception:
        db.rollback()
        max_retries = int(getattr(settings, "MAX_RETRIES", 5))
        n = _retry_count(props) + 1
        if n > max_retries:
            _publish_dlq(channel, body, props)
        else:
            _republish(channel, method.routing_key, body, props, n)
        channel.basic_ack(method.delivery_tag)
    finally:
        db.close()


__all__ = ["_declare", "on_message"]