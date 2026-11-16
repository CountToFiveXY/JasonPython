import json
import unittest
from concurrent.futures import Future

from fastapi import HTTPException
from google.api_core.exceptions import ServiceUnavailable
from pydantic import ValidationError

from src.routers.asphalt_tasks import publish_task
from src.schemas.asphalt_tasks import AsphaltTaskRequest, AsphaltTaskType
from src.services.asphalt_tasks import (
    AsphaltTaskService,
)


class FakePublisher:
    def __init__(self, error=None) -> None:
        self.calls = []
        self.error = error

    @staticmethod
    def topic_path(project_id, topic_id):
        return f"projects/{project_id}/topics/{topic_id}"

    def publish(self, topic, data):
        self.calls.append((topic, data))
        future = Future()
        if self.error is None:
            future.set_result("message-123")
        else:
            future.set_exception(self.error)
        return future


class AsphaltTaskTests(unittest.IsolatedAsyncioTestCase):
    async def test_publishes_reset_with_one_field(self) -> None:
        publisher = FakePublisher()
        response = await publish_task(
            AsphaltTaskRequest(type="RESET"),
            AsphaltTaskService(publisher, "jasonapp-xm0830"),
        )

        self.assertEqual(response.type, AsphaltTaskType.RESET)
        self.assertEqual(response.message_id, "message-123")
        self.assertEqual(
            response.topic,
            "projects/jasonapp-xm0830/topics/asphalt_legend_topic",
        )
        topic, data = publisher.calls[0]
        self.assertEqual(topic, response.topic)
        self.assertEqual(json.loads(data), {"type": "RESET"})
        self.assertEqual(len(json.loads(data)), 1)

    async def test_publishes_refill_ads(self) -> None:
        publisher = FakePublisher()
        service = AsphaltTaskService(publisher, "jasonapp-xm0830")

        published = await service.publish(AsphaltTaskType.REFILL_ADS)

        self.assertEqual(published.type, AsphaltTaskType.REFILL_ADS)
        self.assertEqual(json.loads(publisher.calls[0][1]), {"type": "REFILL_ADS"})

    def test_rejects_unknown_type(self) -> None:
        with self.assertRaises(ValidationError):
            AsphaltTaskRequest(type="UNKNOWN")

    async def test_translates_pubsub_failure(self) -> None:
        publisher = FakePublisher(ServiceUnavailable("offline"))
        service = AsphaltTaskService(publisher, "jasonapp-xm0830")

        with self.assertRaises(HTTPException) as raised:
            await publish_task(
                AsphaltTaskRequest(type="RESET"),
                service,
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("not sent", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
