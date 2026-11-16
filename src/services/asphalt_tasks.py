"""Publish remote Asphalt tasks to Google Cloud Pub/Sub."""

import asyncio
import json
from dataclasses import dataclass

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import pubsub_v1

from src.schemas.asphalt_tasks import AsphaltTaskType


ASPHALT_TASKS_TOPIC = "asphalt_legend_topic"
PUBLISH_TIMEOUT_SECONDS = 10


class AsphaltTaskPublishError(RuntimeError):
    """The task could not be accepted by Pub/Sub."""


@dataclass(frozen=True)
class PublishedAsphaltTask:
    type: AsphaltTaskType
    topic: str
    message_id: str


class AsphaltTaskService:
    def __init__(
        self,
        publisher: pubsub_v1.PublisherClient,
        project_id: str,
    ) -> None:
        self._publisher = publisher
        self._topic = publisher.topic_path(project_id, ASPHALT_TASKS_TOPIC)

    async def publish(
        self,
        task_type: AsphaltTaskType,
    ) -> PublishedAsphaltTask:
        # Keep the wire message deliberately small and stable for the Windows
        # subscriber: its JSON body contains exactly one field.
        data = json.dumps(
            {"type": task_type.value},
            separators=(",", ":"),
        ).encode("utf-8")

        try:
            future = self._publisher.publish(self._topic, data)
            message_id = await asyncio.to_thread(
                future.result,
                timeout=PUBLISH_TIMEOUT_SECONDS,
            )
        except (GoogleAPICallError, TimeoutError) as exc:
            raise AsphaltTaskPublishError(
                "Pub/Sub is unavailable. The Asphalt task was not sent."
            ) from exc

        return PublishedAsphaltTask(
            type=task_type,
            topic=self._topic,
            message_id=message_id,
        )
