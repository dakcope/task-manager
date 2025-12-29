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


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, str(getattr(settings, "LOG_LEVEL", "INFO")).upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    conn = _connect()
    ch = conn.channel()

    _declare(ch)

    prefetch = settings.WORKER_PREFETCH
    ch.basic_qos(prefetch_count=prefetch)

    if settings.WORKER_QUEUES:
        queues = [q.strip() for q in settings.WORKER_QUEUES.split(",") if q.strip()]
    else:
        queues = [settings.TASKS_QUEUE_HIGH, settings.TASKS_QUEUE_MEDIUM, settings.TASKS_QUEUE_LOW]

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