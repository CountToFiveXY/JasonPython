import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from src.temporal.activities import order
from src.temporal.payout_service import OrderPayout, PayoutService, PayoutStatus
from src.temporal.workflows.order import OrderWorkflow, OrderWorkflowInput


def workflow_input() -> OrderWorkflowInput:
    from datetime import datetime, timedelta, timezone

    created = datetime(2026, 9, 11, tzinfo=timezone.utc)
    return OrderWorkflowInput(
        order_id="order-123",
        user_id="user-123",
        created=created.isoformat(),
        expires_at=(created + timedelta(days=1)).isoformat(),
        status="STARTED",
        collection="orders",
    )


class OrderWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_success_signal_releases_workflow(self) -> None:
        workflow = OrderWorkflow()

        await workflow.update_status("PENDING")
        self.assertIsNone(workflow.status)

        await workflow.update_status("SUCCESS")
        self.assertEqual(workflow.status, "SUCCESS")

    async def test_order_complete_updates_existing_document(self) -> None:
        client = Mock()
        document = client.collection.return_value.document.return_value
        with patch.object(order, "firestore_client", return_value=client):
            result = await order.complete("order-123", "orders")

        client.collection.assert_called_once_with("orders")
        client.collection.return_value.document.assert_called_once_with("order-123")
        document.update.assert_called_once_with({"status": "COMPLETED"})
        self.assertEqual(result, "Order order-123 completed")

    async def test_completes_existing_order_after_success_and_payout(self) -> None:
        workflow = OrderWorkflow()
        execute_activity = AsyncMock(return_value="Order order-123 completed")

        async def payout_after_success(*args, **kwargs):
            self.assertEqual(workflow.status, "SUCCESS")
            execute_activity.assert_not_awaited()
            self.assertIsNone(workflow.payout_id)
            await workflow.payout_completed("order-123_payout")
            await workflow.payout_started("unrelated-payout")
            await workflow.payout_started("order-123_payout")
            self.assertEqual(workflow.payout_id, "order-123_payout")
            await workflow.payout_completed("order-123_payout")
            await workflow.payout_started("order-123_payout")
            self.assertEqual(workflow.payout_status, PayoutStatus.COMPLETED)
            return "Hello, user-123!"

        run_payout = AsyncMock(side_effect=payout_after_success)

        async def wait_for_success(condition, **kwargs):
            run_payout.assert_not_awaited()
            self.assertFalse(condition())
            await workflow.update_status("SUCCESS")
            self.assertTrue(condition())

        with (
            patch(
                "src.temporal.workflows.order.workflow.info",
                return_value=SimpleNamespace(workflow_id="order-123", run_id="run-123"),
            ),
            patch(
                "src.temporal.workflows.order.workflow.create_nexus_client",
                return_value=SimpleNamespace(execute_operation=run_payout),
            ) as create_nexus_client,
            patch(
                "src.temporal.workflows.order.workflow.wait_condition",
                side_effect=wait_for_success,
            ),
            patch(
                "src.temporal.workflows.order.workflow.execute_activity",
                execute_activity,
            ),
        ):
            request = workflow_input()
            result = await workflow.run(request)

        self.assertEqual(result, "Order order-123 completed")
        self.assertEqual(create_nexus_client.call_args.kwargs["service"], PayoutService)
        self.assertEqual(
            run_payout.await_args.args,
            (
                PayoutService.run_payout,
                OrderPayout(
                    name="user-123",
                    order_workflow_id="order-123",
                    order_run_id="run-123",
                    order_id="order-123",
                ),
            ),
        )
        execute_activity.assert_awaited_once()
        self.assertEqual(execute_activity.await_args.args, (order.complete,))
        self.assertEqual(execute_activity.await_args.kwargs["args"], ["order-123", "orders"])

    async def test_workflow_completes_with_timeout_result_after_one_hour(self) -> None:
        workflow = OrderWorkflow()
        wait_condition = AsyncMock(side_effect=asyncio.TimeoutError)
        execute_activity = AsyncMock(return_value="written")

        with (
            patch("src.temporal.workflows.order.workflow.create_nexus_client") as create_nexus_client,
            patch("src.temporal.workflows.order.workflow.wait_condition", wait_condition),
            patch(
                "src.temporal.workflows.order.workflow.execute_activity",
                execute_activity,
            ),
        ):
            result = await workflow.run(workflow_input())

        self.assertEqual(result, "Order order-123 timed out waiting for SUCCESS")
        self.assertEqual(wait_condition.await_args.kwargs["timeout"].total_seconds(), 3600)
        execute_activity.assert_not_awaited()
        create_nexus_client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
