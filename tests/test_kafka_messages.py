import unittest
from types import SimpleNamespace

from src.messaging.config import KAFKA_TOPIC
from src.messaging.events import OrderStatusEvent
from src.messaging.worker import handle_message
from src.routers.messages import publish_message
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
    async def test_publishes_message_event_and_returns_metadata(self) -> None:
        producer = FakeProducer()
        response = await publish_message(
            OrderStatusEvent(
                id="12345678-1234-1234-1234-123456789abc",
                status="SUCCESS",
            ),
            producer,
        )

        self.assertEqual(response.id, "12345678-1234-1234-1234-123456789abc")
        self.assertEqual(response.status.value, "SUCCESS")
        self.assertEqual(response.topic, KAFKA_TOPIC)
        self.assertEqual(response.partition, 2)
        self.assertEqual(response.offset, 17)
        topic, event, key = producer.calls[0]
        self.assertEqual(topic, KAFKA_TOPIC)
        self.assertEqual(event, {"id": response.id, "status": "SUCCESS"})
        self.assertEqual(key.decode(), event["id"])

    async def test_worker_signals_matching_order_workflow(self) -> None:
        temporal = FakeTemporalClient()

        await handle_message(
            {"id": "order-123", "status": "SUCCESS"},
            temporal,
        )

        self.assertEqual(temporal.workflow_id, "order-123")
        self.assertEqual(
            temporal.handle.signals,
            [(OrderWorkflow.update_status, "SUCCESS")],
        )


if __name__ == "__main__":
    unittest.main()
