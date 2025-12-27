from dataclasses import dataclass
from uuid import UUID

from app.core.enums import Priority
from app.messaging.rabbitmq import QUEUES, publish


@dataclass(frozen=True)
class TaskPublisher:
    def publish_task_created(self, task_id: UUID, priority: Priority) -> None:
        publish(
            queue_name=_queue_for_priority(priority),
            payload={"task_id": str(task_id), "priority": priority.value},
        )


def _queue_for_priority(priority: Priority) -> str:
    mapping = {
        Priority.HIGH: QUEUES.high,
        Priority.MEDIUM: QUEUES.medium,
        Priority.LOW: QUEUES.low,
    }
    return mapping[priority]