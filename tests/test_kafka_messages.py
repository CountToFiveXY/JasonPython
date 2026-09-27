import unittest
from types import SimpleNamespace

from pydantic import TypeAdapter, ValidationError

from src.infrastructure.scheduler import (
    LocalSchedulerController,
    handle_scheduler_control_message,
)
from src.messaging.config import KAFKA_ORDER_TOPIC, KAFKA_SCHEDULER_TOPIC
from src.messaging.events import (
    MessageEvent,
    OrderMessageEvent,
    OrderStatusEvent,
    SchedulerControlEvent,
    SchedulingMessageEvent,
)
from src.messaging.worker import handle_message
from src.routers.messages import publish_message
from src.services import MessageService
from src.temporal.workflows.order import OrderWorkflow


class FakeProducer:
    def __init__(self) -> None:
        self.calls = []

    async def send_and_wait(self, topic, value, *, key):
        self.calls.append((topic, value, key))
        return SimpleNamespace(topic=topic, partition=2, offset=17)


class FakeWorkflowHandle:
    def __init__(self) -> None:
        self.signals = []

    async def signal(self, signal, value) -> None:
        self.signals.append((signal, value))


class FakeTemporalClient:
    def __init__(self) -> None:
        self.workflow_id = None
        self.handle = FakeWorkflowHandle()

    def get_workflow_handle(self, workflow_id: str) -> FakeWorkflowHandle:
        self.workflow_id = workflow_id
        return self.handle


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

    async def test_publishes_message_event_and_returns_metadata(self) -> None:
        producer = FakeProducer()
        response = await publish_message(
            OrderMessageEvent(
                EventType="ORDER",
                detailed_payload=OrderStatusEvent(
                    id="12345678-1234-1234-1234-123456789abc",
                    status="SUCCESS",
                ),
            ),
            MessageService(producer),
        )

        self.assertEqual(response.event_type.value, "ORDER")
        self.assertEqual(
            response.detailed_payload.id,
            "12345678-1234-1234-1234-123456789abc",
        )
        self.assertEqual(response.detailed_payload.status.value, "SUCCESS")
        self.assertEqual(response.topic, KAFKA_ORDER_TOPIC)
        self.assertEqual(response.partition, 2)
        self.assertEqual(response.offset, 17)
        topic, event, key = producer.calls[0]
        self.assertEqual(topic, KAFKA_ORDER_TOPIC)
        self.assertEqual(
            event,
            {
                "EventType": "ORDER",
                "detailed_payload": {
                    "id": response.detailed_payload.id,
                    "status": "SUCCESS",
                },
            },
        )
        self.assertEqual(key.decode(), event["detailed_payload"]["id"])

    async def test_worker_signals_matching_order_workflow(self) -> None:
        temporal = FakeTemporalClient()

        await handle_message(
            {
                "EventType": "ORDER",
                "detailed_payload": {"id": "order-123", "status": "SUCCESS"},
            },
            temporal,
        )

        self.assertEqual(temporal.workflow_id, "order-123")
        self.assertEqual(
            temporal.handle.signals,
            [(OrderWorkflow.update_status, "SUCCESS")],
        )

    async def test_publishes_scheduler_control_event(self) -> None:
        producer = FakeProducer()
        response = await publish_message(
            SchedulingMessageEvent(
                EventType="SCHEDULING",
                detailed_payload=SchedulerControlEvent(action="STOP"),
            ),
            MessageService(producer),
        )

        self.assertEqual(response.event_type.value, "SCHEDULING")
        self.assertEqual(response.detailed_payload.action.value, "STOP")
        topic, event, key = producer.calls[0]
        self.assertEqual(topic, KAFKA_SCHEDULER_TOPIC)
        self.assertEqual(
            event,
            {
                "EventType": "SCHEDULING",
                "detailed_payload": {"action": "STOP"},
            },
        )
        self.assertEqual(key, b"scheduler:local")

    async def test_scheduler_topic_stops_and_starts_local_scheduler(self) -> None:
        controller = LocalSchedulerController()
        self.assertFalse(controller.enabled)

        await handle_scheduler_control_message(
            {
                "EventType": "SCHEDULING",
                "detailed_payload": {"action": "STOP"},
            },
            controller,
        )
        self.assertFalse(controller.enabled)

        await handle_scheduler_control_message(
            {
                "EventType": "SCHEDULING",
                "detailed_payload": {"action": "START"},
            },
            controller,
        )
        self.assertTrue(controller.enabled)


if __name__ == "__main__":
    unittest.main()
