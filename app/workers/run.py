import logging
import time

import pika

from app.core.config import settings
from app.workers.consumer import _declare, on_message

logger = logging.getLogger(__name__)

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


def _get_queues() -> list[str]:
    raw = getattr(settings, "WORKER_QUEUES", None)
    if raw:
        return [q.strip() for q in raw.split(",") if q.strip()]
    return [settings.TASKS_QUEUE_HIGH, settings.TASKS_QUEUE_MEDIUM, settings.TASKS_QUEUE_LOW]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    conn = _connect()
    ch = conn.channel()

    _declare(ch)

    prefetch = int(getattr(settings, "WORKER_PREFETCH", 1))
    ch.basic_qos(prefetch_count=prefetch)

    queues = _get_queues()
    logger.info(f"Воркер запущен. prefetch={prefetch} queues={queues}")

    for q in queues:
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