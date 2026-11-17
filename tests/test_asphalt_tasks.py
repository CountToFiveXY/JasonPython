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
        self.assertEqual(response.repeat, None)

    async def test_publishes_refill_ads(self) -> None:
        publisher = FakePublisher()
        service = AsphaltTaskService(publisher, "jasonapp-xm0830")

        published = await service.publish(AsphaltTaskType.REFILL_ADS, repeat=12)

        self.assertEqual(published.type, AsphaltTaskType.REFILL_ADS)
        self.assertEqual(published.repeat, 12)
        self.assertEqual(len(publisher.calls), 1)
        self.assertEqual(
            json.loads(publisher.calls[0][1]),
            {"type": "REFILL_ADS", "repeat": 12},
        )

    async def test_publishes_start_game_as_one_message(self) -> None:
        publisher = FakePublisher()
        service = AsphaltTaskService(publisher, "jasonapp-xm0830")

        published = await service.publish(AsphaltTaskType.START_GAME)

        self.assertEqual(published.type, AsphaltTaskType.START_GAME)
        self.assertEqual(published.repeat, None)
        self.assertEqual(len(publisher.calls), 1)
        self.assertEqual(
            json.loads(publisher.calls[0][1]),
            {"type": "START_GAME"},
        )

    async def test_publishes_close_game_as_one_message(self) -> None:
        publisher = FakePublisher()
        service = AsphaltTaskService(publisher, "jasonapp-xm0830")

        published = await service.publish(AsphaltTaskType.CLOSE_GAME)

        self.assertEqual(published.type, AsphaltTaskType.CLOSE_GAME)
        self.assertEqual(published.repeat, None)
        self.assertEqual(len(publisher.calls), 1)
        self.assertEqual(
            json.loads(publisher.calls[0][1]),
            {"type": "CLOSE_GAME"},
        )

    def test_defaults_refill_repeat_to_eight(self) -> None:
        request = AsphaltTaskRequest(type="REFILL_ADS")

        self.assertEqual(request.repeat, 8)

    def test_rejects_refill_repeat_outside_one_to_ninety_nine(self) -> None:
        for repeat in (0, 100):
            with self.subTest(repeat=repeat), self.assertRaises(ValidationError):
                AsphaltTaskRequest(type="REFILL_ADS", repeat=repeat)

    def test_rejects_repeat_for_reset(self) -> None:
        for task_type in ("RESET", "START_GAME", "CLOSE_GAME"):
            with self.subTest(task_type=task_type), self.assertRaises(ValidationError):
                AsphaltTaskRequest(type=task_type, repeat=8)

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
