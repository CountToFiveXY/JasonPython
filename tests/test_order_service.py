import unittest
from unittest.mock import AsyncMock, patch

from src.services.order import (
    ORDER_COLLECTION,
    OrderService,
)
from src.entity import OrderStatus
from src.temporal.workflows.order import OrderWorkflow, OrderWorkflowInput


class OrderServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_creates_order_and_starts_workflows_with_same_id(self) -> None:
        temporal = AsyncMock()
        service = OrderService(temporal)

        with patch(
            "src.services.order.uuid4",
            return_value="12345678-1234-1234-1234-123456789abc",
        ):
            order = await service.create("user-123")

        self.assertEqual(order.id, "12345678-1234-1234-1234-123456789abc")
        self.assertEqual(order.user_id, "user-123")
        self.assertEqual(order.status, OrderStatus.STARTED)
        self.assertIsNotNone(order.created.tzinfo)
        self.assertEqual(
            (order.expires_at - order.created).total_seconds(),
            86_400,
        )
        temporal.start_workflow.assert_awaited_once()

        order_call = temporal.start_workflow.await_args
        workflow_run, workflow_input = order_call.args
        self.assertEqual(workflow_run, OrderWorkflow.run)
        self.assertIsInstance(workflow_input, OrderWorkflowInput)
        self.assertEqual(workflow_input.order_id, order.id)
        self.assertEqual(workflow_input.user_id, order.user_id)
        self.assertEqual(workflow_input.created, order.created.isoformat())
        self.assertEqual(workflow_input.expires_at, order.expires_at.isoformat())
        self.assertEqual(workflow_input.status, "STARTED")
        self.assertEqual(workflow_input.collection, ORDER_COLLECTION)
        self.assertEqual(order_call.kwargs["id"], order.id)


if __name__ == "__main__":
    unittest.main()
