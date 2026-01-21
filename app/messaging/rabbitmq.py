import json
import logging
import threading
from dataclasses import dataclass
from typing import Any, Mapping

import pika
import time
from pika.adapters.blocking_connection import BlockingChannel

from app.core.config import settings

logger = logging.getLogger(__name__)

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
    for i in range(60):
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


class RabbitMQPublisher:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._connection: pika.BlockingConnection | None = None
        self._channel: BlockingChannel | None = None

    def _ensure(self) -> BlockingChannel:
        if self._connection and self._channel and self._connection.is_open and self._channel.is_open:
            return self._channel

        self._connection = _connect()
        self._channel = self._connection.channel()
        _declare_queues(self._channel)
        return self._channel

    def publish(self, *, queue_name: str, payload: Mapping[str, Any]) -> None:
        if not settings.RABBITMQ_ENABLED:
            return

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        with self._lock:
            ch = self._ensure()
            try:
                ch.basic_publish(
                    exchange="",
                    routing_key=queue_name,
                    body=body,
                    properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
                )
            except Exception:
                try:
                    if self._connection and self._connection.is_open:
                        self._connection.close()
                finally:
                    self._connection = None
                    self._channel = None
                raise


_publisher = RabbitMQPublisher()


def publish(queue_name: str, payload: Mapping[str, Any]) -> None:
    _publisher.publish(queue_name=queue_name, payload=payload)