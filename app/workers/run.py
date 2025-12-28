import time

import pika

from app.core.config import settings
from app.workers.consumer import _declare, on_message


def _connect() -> pika.BlockingConnection:
    params = pika.URLParameters(settings.RABBITMQ_URL)
    last = None
    for _ in range(120):
        try:
            return pika.BlockingConnection(params)
        except Exception as e:
            last = e
            time.sleep(1)
    raise last


def main() -> None:
    conn = _connect()
    ch = conn.channel()

    _declare(ch)

    prefetch = int(getattr(settings, "WORKER_PREFETCH", 1))
    ch.basic_qos(prefetch_count=prefetch)

    for q in (settings.TASKS_QUEUE_HIGH, settings.TASKS_QUEUE_MEDIUM, settings.TASKS_QUEUE_LOW):
        ch.basic_consume(queue=q, on_message_callback=on_message, auto_ack=False)

    try:
        ch.start_consuming()
    finally:
        try:
            ch.stop_consuming()
        except Exception:
            pass
        conn.close()


if __name__ == "__main__":
    main()