import json
import logging
from datetime import datetime, timezone
from uuid import UUID

import pika
from sqlalchemy import update

from app.core.config import settings
from app.core.enums import TaskStatus
from app.db.models.task import Task
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

RETRY_DELAYS_SECONDS: list[int] = [1, 5, 30, 120]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _retry_queue_name(routing_key: str, delay_seconds: int) -> str:
    return f"{routing_key}.retry.{delay_seconds}s"


def _declare(channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
    base = (settings.TASKS_QUEUE_HIGH, settings.TASKS_QUEUE_MEDIUM, settings.TASKS_QUEUE_LOW)
    for q in (*base, "tasks.dlq"):
        channel.queue_declare(queue=q, durable=True)

    for q in base:
        for delay in RETRY_DELAYS_SECONDS:
            channel.queue_declare(
                queue=_retry_queue_name(q, delay),
                durable=True,
                arguments={
                    "x-message-ttl": int(delay * 1000),
                    "x-dead-letter-exchange": "",
                    "x-dead-letter-routing-key": q,
                },
            )


def _retry_count(props: pika.BasicProperties) -> int:
    v = (props.headers or {}).get("x-retry-count", 0)
    try:
        return int(v)
    except Exception:
        return 0


def _republish(channel, routing_key: str, body: bytes, props: pika.BasicProperties, retry_count: int) -> None:
    headers = dict(props.headers or {})
    headers["x-retry-count"] = retry_count
    delay = RETRY_DELAYS_SECONDS[min(retry_count - 1, len(RETRY_DELAYS_SECONDS) - 1)]
    channel.basic_publish(
        exchange="",
        routing_key=_retry_queue_name(routing_key, delay),
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
    routing_key = getattr(method, "routing_key", "unknown")
    try:
        task_id = _parse(body)
    except Exception:
        logger.warning(f"Невалидное сообщение. queue={routing_key}")
        _publish_dlq(channel, body, props)
        channel.basic_ack(method.delivery_tag)
        return

    db = SessionLocal()
    try:
        if not _claim(db, task_id):
            db.commit()
            logger.info(f"Задача пропущена: нет статуса  PENDING. task_id={task_id} queue={routing_key}")
            channel.basic_ack(method.delivery_tag)
            return

        try:
            logger.info(f"Старт обработки задачи. task_id={task_id} queue={routing_key}")
            result = _execute(task_id)
            _complete(db, task_id, result)
            db.commit()
            logger.info(f"Задача завершена успешно. task_id={task_id}")
            channel.basic_ack(method.delivery_tag)
            return
        except Exception as e:
            _fail(db, task_id, str(e))
            db.commit()
            logger.exception(f"Ошибка обработки задачи. task_id={task_id}")
            channel.basic_ack(method.delivery_tag)
            return

    except Exception:
        db.rollback()
        max_retries = int(getattr(settings, "MAX_RETRIES", 5))
        n = _retry_count(props) + 1
        if n > max_retries:
            _publish_dlq(channel, body, props)
            logger.exception(f"Не удалось обработать, экспорт в dlq. task_id={task_id} queue={routing_key} retries={n}")
        else:
            _republish(channel, routing_key, body, props, n)
            delay = RETRY_DELAYS_SECONDS[min(n - 1, len(RETRY_DELAYS_SECONDS) - 1)]
            logger.exception(
                f"Ошибка обработки, повтор через {delay}сек. task_id={task_id} queue={routing_key} retries={n}"
            )

        channel.basic_ack(method.delivery_tag)
    finally:
        db.close()


__all__ = ["_declare", "on_message"]