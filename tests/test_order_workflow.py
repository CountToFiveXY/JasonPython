import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from src.temporal.activities.firestore import write_firestore_document
from src.temporal.activities.order import complete_order
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

    async def test_completion_activity_returns_order_result(self) -> None:
        result = await complete_order("order-123")
        self.assertEqual(result, "Order order-123 completed")

    async def test_persists_started_then_completed_after_success(self) -> None:
        workflow = OrderWorkflow()
        await workflow.update_status("SUCCESS")
        execute_activity = AsyncMock(
            side_effect=["written", "Order order-123 completed", "updated"]
        )

        with (
            patch(
                "src.temporal.workflows.order.workflow.wait_condition",
                AsyncMock(),
            ),
            patch(
                "src.temporal.workflows.order.workflow.execute_activity",
                execute_activity,
            ),
            patch(
                "src.temporal.workflows.order.workflow.patched",
                return_value=True,
            ),
        ):
            result = await workflow.run(workflow_input())

        self.assertEqual(result, "Order order-123 completed")
        calls = execute_activity.await_args_list
        initial_write = calls[0].args[1]
        self.assertEqual(initial_write.fields["status"], "STARTED")
        self.assertFalse(initial_write.merge)
        self.assertEqual(calls[1].args, (complete_order, "order-123"))
        completion_write = calls[2].args[1]
        self.assertEqual(completion_write.fields, {"status": "COMPLETED"})
        self.assertTrue(completion_write.merge)

    async def test_workflow_completes_with_timeout_result_after_one_hour(self) -> None:
        workflow = OrderWorkflow()
        wait_condition = AsyncMock(side_effect=asyncio.TimeoutError)
        execute_activity = AsyncMock(return_value="written")

        with (
            patch("src.temporal.workflows.order.workflow.wait_condition", wait_condition),
            patch(
                "src.temporal.workflows.order.workflow.execute_activity",
                execute_activity,
            ),
        ):
            result = await workflow.run(workflow_input())

        self.assertEqual(result, "Order order-123 timed out waiting for SUCCESS")
        self.assertEqual(wait_condition.await_args.kwargs["timeout"].total_seconds(), 3600)
        self.assertEqual(execute_activity.await_args.args[0], write_firestore_document)


if __name__ == "__main__":
    unittest.main()
