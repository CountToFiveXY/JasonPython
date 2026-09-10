import asyncio
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.temporal.activities.order import complete_order


@workflow.defn
class OrderWorkflow:
    def __init__(self) -> None:
        self.status: str | None = None

    @workflow.signal
    async def update_status(self, status: str) -> None:
        if status == "SUCCESS":
            self.status = status

    @workflow.run
    async def run(self, order_id: str) -> str:
        try:
            await workflow.wait_condition(
                lambda: self.status == "SUCCESS",
                timeout=timedelta(hours=1),
                timeout_summary="wait-for-order-success",
            )
        except asyncio.TimeoutError:
            return f"Order {order_id} timed out waiting for SUCCESS"

        return await workflow.execute_activity(
            complete_order,
            order_id,
            start_to_close_timeout=timedelta(seconds=30),
        )
