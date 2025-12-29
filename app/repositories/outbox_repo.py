from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import OutboxStatus
from app.db.models.outbox import OutboxEvent


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class OutboxRepository:
    db: Session

    def add(self, event: OutboxEvent) -> None:
        self.db.add(event)

    def fetch_batch_for_publish(self, *, limit: int) -> list[OutboxEvent]:
        stmt = (
            select(OutboxEvent)
            .where(
                OutboxEvent.status == OutboxStatus.NEW,
                OutboxEvent.next_attempt_at <= utcnow(),
            )
            .order_by(OutboxEvent.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(self.db.scalars(stmt).all())