import unittest
from unittest.mock import AsyncMock, patch

from src.temporal.workflows.order_cleanup import OrderCleanupWorkflow


class OrderCleanupWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_waits_one_day_then_deletes_order(self) -> None:
        sleep = AsyncMock()
        execute_activity = AsyncMock(return_value="Expired order order-123 deleted")

        with (
            patch("src.temporal.workflows.order_cleanup.workflow.sleep", sleep),
            patch(
                "src.temporal.workflows.order_cleanup.workflow.execute_activity",
                execute_activity,
            ),
        ):
            result = await OrderCleanupWorkflow().run("order-123")

        self.assertEqual(sleep.await_args.args[0].total_seconds(), 86_400)
        self.assertEqual(result, "Expired order order-123 deleted")


if __name__ == "__main__":
    unittest.main()
