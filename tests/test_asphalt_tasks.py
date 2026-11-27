import json
import unittest
from concurrent.futures import Future
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from uuid import uuid4

from fastapi import HTTPException
from google.api_core.exceptions import ServiceUnavailable
from pydantic import ValidationError

from src.routers.asphalt_tasks import publish_task
from src.messaging.refill_results import SUBSCRIPTION, consume_results
from src.repositories.asphalt_tasks import AsphaltTasks
from src.schemas.asphalt_tasks import AsphaltTaskRequest, AsphaltTaskType, RefillStatus
from src.services.asphalt_tasks import (
    AsphaltTaskService,
)


class FakePublisher:
    def __init__(self, error=None) -> None:
        self.calls = []
        self.error = error
        self.attributes = []

    @staticmethod
    def topic_path(project_id, topic_id):
        return f"projects/{project_id}/topics/{topic_id}"

    def publish(self, topic, data, **attributes):
        self.calls.append((topic, data))
        self.attributes.append(attributes)
        future = Future()
        if self.error is None:
            future.set_result("message-123")
        else:
            future.set_exception(self.error)
        return future


class AsphaltTaskTests(unittest.IsolatedAsyncioTestCase):
    def service(self, publisher):
        return AsphaltTaskService(publisher, "jasonapp-xm0830", Mock())

    def test_stores_and_reads_task_type_in_shared_collection(self):
        client = Mock()
        collection = client.collection.return_value
        document = collection.document.return_value
        task_id = uuid4()
        tasks = AsphaltTasks(client)

        tasks.create(task_id, AsphaltTaskType.REFILL_ADS, 8)

        client.collection.assert_called_once_with("asphalt_tasks")
        collection.document.assert_called_once_with(str(task_id))
        data = document.create.call_args.args[0]
        self.assertEqual(data["type"], "REFILL_ADS")
        self.assertEqual(data["status"], "QUEUED")
        self.assertEqual(data["repeat"], 8)

        document.get.return_value.to_dict.return_value = data
        result = tasks.get(task_id)
        self.assertEqual(result.type, AsphaltTaskType.REFILL_ADS)
        self.assertEqual(result.status, RefillStatus.QUEUED)

    def test_recent_tasks_include_legacy_refills_and_sort_by_request_time(self):
        client = Mock()
        collection = client.collection.return_value
        now = datetime.now(timezone.utc)
        newer = Mock(id=str(uuid4()))
        newer.to_dict.return_value = {"type": "MUTE", "status": "SUBMITTED", "created_at": now}
        legacy = Mock(id=str(uuid4()), create_time=now - timedelta(minutes=1))
        legacy.to_dict.return_value = {"type": "REFILL_ADS", "status": "SUCCEEDED", "repeat": 8}
        created, updated = Mock(), Mock()
        collection.order_by.side_effect = [created, updated]
        created.limit.return_value.stream.return_value = [newer]
        updated.limit.return_value.stream.return_value = [legacy, newer]

        rows = AsphaltTasks(client).recent()

        self.assertEqual([str(row.task_id) for row in rows], [newer.id, legacy.id])
        self.assertEqual(rows[0].status, RefillStatus.SUBMITTED)
        self.assertEqual(rows[1].repeat, 8)
        created.limit.assert_called_once_with(10)

    def test_consumer_acknowledges_only_after_storing_result(self):
        subscriber, tasks = Mock(), Mock()
        consume_results(subscriber, tasks)
        self.assertEqual(subscriber.subscribe.call_args.args, (SUBSCRIPTION,))
        callback = subscriber.subscribe.call_args.kwargs["callback"]
        task_id = uuid4()
        payload = json.dumps({"task_id": str(task_id), "status": "SUCCEEDED"}).encode()
        message = Mock(data=payload)

        def store(result):
            message.ack.assert_not_called()
            self.assertEqual(result.task_id, task_id)
            self.assertEqual(result.status, RefillStatus.SUCCEEDED)

        tasks.apply.side_effect = store
        callback(message)
        message.ack.assert_called_once()

        retry = Mock(data=payload)
        tasks.apply.side_effect = ServiceUnavailable("offline")
        with self.assertLogs("src.messaging.refill_results", level="ERROR"):
            callback(retry)
        retry.ack.assert_not_called()
        retry.nack.assert_called_once()

    async def test_publishes_reset_with_one_field(self) -> None:
        publisher = FakePublisher()
        response = await publish_task(
            AsphaltTaskRequest(type="RESET"),
            self.service(publisher),
        )

        self.assertEqual(response.type, AsphaltTaskType.RESET)
        self.assertEqual(response.message_id, "message-123")
        self.assertEqual(
            response.topic,
            "projects/jasonapp-xm0830/topics/asphalt_task_requests",
        )
        topic, data = publisher.calls[0]
        self.assertEqual(topic, response.topic)
        self.assertEqual(json.loads(data), {"type": "RESET"})
        self.assertEqual(len(json.loads(data)), 1)
        self.assertEqual(response.repeat, None)

    async def test_publishes_refill_ads(self) -> None:
        publisher = FakePublisher()
        tasks = Mock()
        service = AsphaltTaskService(publisher, "jasonapp-xm0830", tasks)
        published = await publish_task(AsphaltTaskRequest(type="REFILL_ADS", repeat=12), service)

        self.assertEqual(published.type, AsphaltTaskType.REFILL_ADS)
        self.assertEqual(published.repeat, 12)
        tasks.create.assert_called_once_with(published.task_id, AsphaltTaskType.REFILL_ADS, 12)
        self.assertIsNotNone(published.task_id)
        self.assertEqual(publisher.attributes, [{"task_id": str(published.task_id)}])
        self.assertEqual(len(publisher.calls), 1)
        self.assertEqual(
            json.loads(publisher.calls[0][1]),
            {"type": "REFILL_ADS", "repeat": 12},
        )

    async def test_publishes_start_game_as_one_message(self) -> None:
        publisher = FakePublisher()
        service = self.service(publisher)

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
        service = self.service(publisher)

        published = await service.publish(AsphaltTaskType.CLOSE_GAME)

        self.assertEqual(published.type, AsphaltTaskType.CLOSE_GAME)
        self.assertEqual(published.repeat, None)
        self.assertEqual(len(publisher.calls), 1)
        self.assertEqual(
            json.loads(publisher.calls[0][1]),
            {"type": "CLOSE_GAME"},
        )

    async def test_publishes_window_as_one_message(self) -> None:
        publisher = FakePublisher()
        service = self.service(publisher)

        published = await service.publish(AsphaltTaskType.WINDOW)

        self.assertEqual(published.type, AsphaltTaskType.WINDOW)
        self.assertEqual(published.repeat, None)
        self.assertEqual(len(publisher.calls), 1)
        self.assertEqual(
            json.loads(publisher.calls[0][1]),
            {"type": "WINDOW"},
        )

    async def test_publishes_mute_as_one_message(self) -> None:
        publisher = FakePublisher()
        service = self.service(publisher)

        published = await service.publish(AsphaltTaskType.MUTE)

        self.assertEqual(published.type, AsphaltTaskType.MUTE)
        self.assertEqual(published.repeat, None)
        self.assertEqual(len(publisher.calls), 1)
        self.assertEqual(
            json.loads(publisher.calls[0][1]),
            {"type": "MUTE"},
        )

    def test_defaults_refill_repeat_to_eight(self) -> None:
        request = AsphaltTaskRequest(type="REFILL_ADS")

        self.assertEqual(request.repeat, 8)

    def test_rejects_refill_repeat_outside_one_to_ninety_nine(self) -> None:
        for repeat in (0, 100):
            with self.subTest(repeat=repeat), self.assertRaises(ValidationError):
                AsphaltTaskRequest(type="REFILL_ADS", repeat=repeat)

    def test_rejects_repeat_for_reset(self) -> None:
        for task_type in ("RESET", "START_GAME", "CLOSE_GAME", "WINDOW", "MUTE"):
            with self.subTest(task_type=task_type), self.assertRaises(ValidationError):
                AsphaltTaskRequest(type=task_type, repeat=8)

    def test_rejects_unknown_type(self) -> None:
        with self.assertRaises(ValidationError):
            AsphaltTaskRequest(type="UNKNOWN")

    async def test_translates_pubsub_failure(self) -> None:
        publisher = FakePublisher(ServiceUnavailable("offline"))
        service = self.service(publisher)

        with self.assertRaises(HTTPException) as raised:
            await publish_task(
                AsphaltTaskRequest(type="RESET"),
                service,
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("not sent", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
