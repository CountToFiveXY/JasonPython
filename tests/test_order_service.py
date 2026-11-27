import unittest
from unittest.mock import ANY, AsyncMock, Mock, patch

from src.services.order import (
    ORDER_COLLECTION,
    OrderService,
)
from src.entity import OrderStatus
from src.temporal.payout_service import OrderPayout, PayoutStatus
from src.temporal.workflows.order import OrderWorkflow, OrderWorkflowInput


class OrderServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_creates_order_and_starts_workflows_with_same_id(self) -> None:
        writes = Mock()
        document = writes.collection.return_value.document.return_value
        temporal = AsyncMock()
        service = OrderService(temporal)

        async def verify_document_exists(*args, **kwargs):
            document.create.assert_called_once()

        temporal.start_workflow.side_effect = verify_document_exists

        with (
            patch(
                "src.services.order.uuid4",
                return_value="12345678-1234-1234-1234-123456789abc",
            ),
            patch("src.services.order.firestore_client", return_value=writes),
        ):
            order = await service.create("user-123")

        self.assertEqual(order.id, "12345678-1234-1234-1234-123456789abc")
        self.assertEqual(order.user_id, "user-123")
        self.assertEqual(order.status, OrderStatus.STARTED)
        self.assertIsNotNone(order.created.tzinfo)
        self.assertEqual(
            (order.expires_at - order.created).total_seconds(),
            259_200,
        )
        writes.collection.assert_called_once_with(ORDER_COLLECTION)
        writes.collection.return_value.document.assert_called_once_with(order.id)
        document.create.assert_called_once_with({
            "id": order.id,
            "user_id": "user-123",
            "created": order.created,
            "expires_at": order.expires_at,
            "status": "STARTED",
        })
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


    async def test_skips_workflow_start_if_firestore_create_fails(self) -> None:
        temporal = AsyncMock()
        client = Mock()
        client.collection.return_value.document.return_value.create.side_effect = RuntimeError("write failed")
        with patch("src.services.order.firestore_client", return_value=client):
            with self.assertRaisesRegex(RuntimeError, "write failed"):
                await OrderService(temporal).create("user-123")

        temporal.start_workflow.assert_not_awaited()


    async def test_payout_notification_signals_before_updating_order(self) -> None:
        temporal = Mock()
        handle = temporal.get_workflow_handle.return_value
        handle.signal = AsyncMock()
        request = OrderPayout("user-123", "order-123", "run-123", "order-123")

        def verify_signal_sent(*args):
            handle.signal.assert_awaited_once_with(
                OrderWorkflow.payout_started, "order-123_payout", rpc_timeout=ANY
            )

        with patch("src.services.order._write_order_payout", side_effect=verify_signal_sent) as write:
            await OrderService(temporal).receive_payout_status(
                request, "order-123_payout", PayoutStatus.STARTED
            )

        temporal.get_workflow_handle.assert_called_once_with("order-123", run_id="run-123")
        write.assert_called_once_with(request, "order-123_payout", PayoutStatus.STARTED)


if __name__ == "__main__":
    unittest.main()
