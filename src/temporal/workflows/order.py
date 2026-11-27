import asyncio
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.temporal.activities import order
    from src.temporal.activities.order import OrderWorkflowInput
    from src.temporal.config import PAYOUT_NEXUS
    from src.temporal.payout_service import PayoutService, OrderPayout


@workflow.defn
class OrderWorkflow:
    def __init__(self) -> None:
        self.status: str | None = None

    @workflow.signal
    async def update_status(self, status: str) -> None:
        if status == "SUCCESS":
            self.status = status

    @workflow.run
    async def run(self, request: OrderWorkflowInput) -> str:
        await workflow.execute_activity(
            order.create,
            request,
            start_to_close_timeout=timedelta(seconds=30),
        )

        try:
            await workflow.wait_condition(
                lambda: self.status == "SUCCESS",
                timeout=timedelta(hours=1),
                timeout_summary="wait-for-order-success",
            )
        except asyncio.TimeoutError:
            return f"Order {request.order_id} timed out waiting for SUCCESS"

        payout = workflow.create_nexus_client(
            endpoint=PAYOUT_NEXUS, service=PayoutService
        )
        await payout.execute_operation(
            PayoutService.run_payout,
            OrderPayout(
                workflow_id=f"order-payout-{workflow.info().run_id}",
                name=request.user_id,
            ),
            schedule_to_close_timeout=timedelta(minutes=2),
        )

        return await workflow.execute_activity(
            order.complete,
            args=[request.order_id, request.collection],
            start_to_close_timeout=timedelta(seconds=30),
        )
