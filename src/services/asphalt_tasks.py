"""Publish remote Asphalt tasks to Google Cloud Pub/Sub."""

import asyncio
import json
from dataclasses import dataclass
from uuid import UUID, uuid4

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import pubsub_v1

from src.schemas.asphalt_tasks import AsphaltTaskType
from src.repositories.asphalt_tasks import AsphaltTasks


ASPHALT_TASKS_TOPIC = "asphalt_task_requests"
PUBLISH_TIMEOUT_SECONDS = 10


class AsphaltTaskPublishError(RuntimeError):
    """The task could not be accepted by Pub/Sub."""


@dataclass(frozen=True)
class PublishedAsphaltTask:
    type: AsphaltTaskType
    repeat: int | None
    topic: str
    message_id: str
    task_id: UUID | None


class AsphaltTaskService:
    def __init__(
        self,
        publisher: pubsub_v1.PublisherClient,
        project_id: str,
        tasks: AsphaltTasks,
    ) -> None:
        self._publisher = publisher
        self._topic = publisher.topic_path(project_id, ASPHALT_TASKS_TOPIC)
        self._tasks = tasks

    async def publish(
        self,
        task_type: AsphaltTaskType,
        repeat: int | None = None,
    ) -> PublishedAsphaltTask:
        payload: dict[str, str | int] = {"type": task_type.value}
        task_id = None
        if task_type == AsphaltTaskType.REFILL_ADS:
            repeat = 8 if repeat is None else repeat
            if not 1 <= repeat <= 99:
                raise ValueError("repeat must be between 1 and 99")
            payload["repeat"] = repeat
            task_id = uuid4()
        elif repeat is not None:
            raise ValueError("repeat is only supported for REFILL_ADS")

        data = json.dumps(
            payload,
            separators=(",", ":"),
        ).encode("utf-8")

        try:
            attributes = {}
            if task_id is not None:
                await asyncio.to_thread(self._tasks.create, task_id, task_type, repeat)
                attributes["task_id"] = str(task_id)
            future = self._publisher.publish(self._topic, data, **attributes)
            message_id = await asyncio.to_thread(
                future.result,
                timeout=PUBLISH_TIMEOUT_SECONDS,
            )
        except TimeoutError as exc:
            if task_id is not None:
                raise AsphaltTaskPublishError(
                    f"Could not confirm whether the refill was queued. Check task {task_id} before retrying."
                ) from exc
            raise AsphaltTaskPublishError("Could not confirm whether the Asphalt task was queued.") from exc
        except GoogleAPICallError as exc:
            raise AsphaltTaskPublishError(
                "Pub/Sub is unavailable. The Asphalt task was not sent."
            ) from exc

        return PublishedAsphaltTask(
            type=task_type,
            repeat=repeat,
            topic=self._topic,
            message_id=message_id,
            task_id=task_id,
        )
