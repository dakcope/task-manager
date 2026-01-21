import logging
import time
from datetime import timedelta

from sqlalchemy import update

from app.core.config import settings
from app.core.enums import OutboxStatus
from app.db.models.outbox import OutboxEvent
from app.db.session import SessionLocal
from app.messaging.rabbitmq import publish
from app.repositories.outbox_repo import OutboxRepository, utcnow

logger = logging.getLogger(__name__)


def _backoff(attempt: int) -> timedelta:
    return timedelta(seconds=min(60.0, 0.5 * (2 ** max(0, attempt - 1))))


def run_forever() -> None:
    logger.info(f"Outbox запущен. interval={settings.OUTBOX_POLL_INTERVAL}s batch={settings.OUTBOX_BATCH_SIZE}")

    while True:
        db = SessionLocal()
        try:
            repo = OutboxRepository(db)
            events = repo.fetch_batch_for_publish(limit=settings.OUTBOX_BATCH_SIZE)

            if not events:
                db.commit()
                time.sleep(settings.OUTBOX_POLL_INTERVAL)
                continue

            for ev in events:
                try:
                    publish(queue_name=ev.routing_key, payload=ev.payload)
                    db.execute(
                        update(OutboxEvent)
                        .where(OutboxEvent.id == ev.id)
                        .values(status=OutboxStatus.SENT, sent_at=utcnow(), last_error=None)
                    )
                    logger.info(f"Outbox отправил сообщение. outbox_id={ev.id} task_id={ev.task_id} queue={ev.routing_key}")
                except Exception as exc:
                    attempts = int(ev.attempts or 0) + 1
                    next_at = utcnow() + _backoff(attempts)
                    status = OutboxStatus.FAILED if attempts >= settings.OUTBOX_MAX_ATTEMPTS else OutboxStatus.NEW

                    db.execute(
                        update(OutboxEvent)
                        .where(OutboxEvent.id == ev.id)
                        .values(status=status, attempts=attempts, next_attempt_at=next_at, last_error=str(exc))
                    )

                    if status == OutboxStatus.FAILED:
                        logger.exception(
                            f"Outbox не смог отправить сообщение, попытки исчерпаны. outbox_id={ev.id} task_id={ev.task_id} queue={ev.routing_key} attempts={attempts}"
                        )
                    else:
                        logger.exception(
                            f"Outbox не смог отправить сообщение. outbox_id={ev.id} task_id={ev.task_id} queue={ev.routing_key} attempts={attempts} next={next_at.isoformat()}"
                        )

            db.commit()

        except Exception:
            db.rollback()
            logger.exception("Ошибка в цикле")
            time.sleep(1.0)
        finally:
            db.close()