import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from src.temporal.activities.order import complete_order
from src.temporal.workflows.order import OrderWorkflow


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

    async def test_workflow_completes_with_timeout_result_after_one_hour(self) -> None:
        workflow = OrderWorkflow()
        wait_condition = AsyncMock(side_effect=asyncio.TimeoutError)

        with patch("src.temporal.workflows.order.workflow.wait_condition", wait_condition):
            result = await workflow.run("order-123")

        self.assertEqual(result, "Order order-123 timed out waiting for SUCCESS")
        self.assertEqual(wait_condition.await_args.kwargs["timeout"].total_seconds(), 3600)


if __name__ == "__main__":
    unittest.main()
