import json
from dataclasses import dataclass
from typing import Any, Mapping

import pika
import time
from pika.adapters.blocking_connection import BlockingChannel

from app.core.config import settings


@dataclass(frozen=True)
class RabbitQueues:
    high: str
    medium: str
    low: str


QUEUES = RabbitQueues(
    high=settings.TASKS_QUEUE_HIGH,
    medium=settings.TASKS_QUEUE_MEDIUM,
    low=settings.TASKS_QUEUE_LOW,
)


def _connect() -> pika.BlockingConnection:
    params = pika.URLParameters(settings.RABBITMQ_URL)
    last = None
    for _ in range(60):
        try:
            return pika.BlockingConnection(params)
        except Exception as e:
            last = e
            time.sleep(1)
    raise last


def _declare_queues(channel: BlockingChannel) -> None:
    channel.queue_declare(queue=QUEUES.high, durable=True)
    channel.queue_declare(queue=QUEUES.medium, durable=True)
    channel.queue_declare(queue=QUEUES.low, durable=True)


def publish(queue_name: str, payload: Mapping[str, Any]) -> None:
    if not settings.RABBITMQ_ENABLED:
        return

    connection = _connect()
    try:
        channel = connection.channel()
        _declare_queues(channel)

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        channel.basic_publish(
            exchange="",
            routing_key=queue_name,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
            ),
        )
    finally:
        connection.close()