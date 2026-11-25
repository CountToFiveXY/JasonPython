import json
import unittest
from concurrent.futures import Future
from unittest.mock import AsyncMock, Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from types import SimpleNamespace

from pydantic import TypeAdapter, ValidationError

from src.infrastructure.scheduler import LocalSchedulerController
from src.messaging.config import ORDER_SUCCESS_TOPIC
from src.messaging.events import (
    MessageEvent,
    OrderMessageEvent,
    OrderStatusEvent,
    SchedulerControlEvent,
    SchedulingMessageEvent,
)
from src.messaging.worker import handle_message
from src.routers.messages import publish_message, router
from src.temporal.workflows.order import OrderWorkflow


class FakePublisher:
    def __init__(self) -> None:
        self.calls = []

    def publish(self, topic, data):
        self.calls.append((topic, json.loads(data)))
        future = Future()
        future.set_result("message-123")
        return future


def request_with(**state):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(**state)))


def order_event():
    return OrderMessageEvent(
        EventType="ORDER",
        detailed_payload=OrderStatusEvent(id="order-123", status="SUCCESS"),
    )


class MessageTests(unittest.IsolatedAsyncioTestCase):
    def test_event_type_enforces_its_detailed_payload(self) -> None:
        adapter = TypeAdapter(MessageEvent)

        with self.assertRaises(ValidationError):
            adapter.validate_python(
                {
                    "EventType": "SCHEDULING",
                    "detailed_payload": {"id": "order-123", "status": "SUCCESS"},
                }
            )

    def test_publishes_success_to_topic_and_returns_message_id(self) -> None:
        publisher = FakePublisher()
        app = FastAPI()
        app.include_router(router)
        app.state.pubsub_publisher = publisher
        event = {
            "EventType": "ORDER",
            "detailed_payload": {"id": "order-123", "status": "SUCCESS"},
        }

        with TestClient(app) as client:
            response = client.post("/v1/messages", json=event)

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), {
            **event, "topic": ORDER_SUCCESS_TOPIC, "message_id": "message-123"
        })
        self.assertEqual(publisher.calls, [(ORDER_SUCCESS_TOPIC, event)])

    async def test_worker_signals_matching_order_before_acknowledging(self) -> None:
        message = Mock(data=order_event().model_dump_json(by_alias=True).encode())
        temporal = Mock()
        handle = temporal.get_workflow_handle.return_value

        async def signal(method, value, *, rpc_timeout):
            message.ack.assert_not_called()
            self.assertEqual((method, value), (OrderWorkflow.update_status, "SUCCESS"))

        handle.signal = AsyncMock(side_effect=signal)
        await handle_message(message, temporal)

        temporal.get_workflow_handle.assert_called_once_with("order-123")
        handle.signal.assert_awaited_once()
        message.ack.assert_called_once()
        message.nack.assert_not_called()

    async def test_worker_retries_signal_errors(self) -> None:
        message = Mock(data=order_event().model_dump_json(by_alias=True).encode())
        temporal = Mock()
        temporal.get_workflow_handle.return_value.signal = AsyncMock(side_effect=TimeoutError)
        with self.assertLogs("src.messaging.worker", level="ERROR"):
            await handle_message(message, temporal)
        message.nack.assert_called_once()
        message.ack.assert_not_called()

    async def test_worker_discards_invalid_payload(self) -> None:
        message = Mock(data=b"invalid")
        temporal = Mock()
        with self.assertLogs("src.messaging.worker", level="WARNING"):
            await handle_message(message, temporal)
        message.ack.assert_called_once()
        temporal.get_workflow_handle.assert_not_called()

    async def test_scheduler_control_applies_locally(self) -> None:
        controller = LocalSchedulerController()
        for action in ("START", "STOP"):
            response = await publish_message(
                SchedulingMessageEvent(
                    EventType="SCHEDULING",
                    detailed_payload=SchedulerControlEvent(action=action),
                ),
                request_with(scheduler_controller=controller),
            )
            self.assertEqual(response.detailed_payload.action.value, action)
            self.assertEqual(controller.enabled, action == "START")


if __name__ == "__main__":
    unittest.main()
