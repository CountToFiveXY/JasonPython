import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.exceptions import ApplicationError

with workflow.unsafe.imports_passed_through():
    from src.temporal.activities import order
    from src.temporal.activities.order import OrderWorkflowInput
    from src.temporal.config import PAYOUT_NEXUS
    from src.temporal.payout_service import OrderPayout, PayoutService, PayoutStatus


@workflow.defn
class OrderWorkflow:
    def __init__(self) -> None:
        self.status: str | None = None
        self.payout_id: str | None = None
        self.payout_status: PayoutStatus | None = None
        self._expected_payout_id: str | None = None

    @workflow.signal
    async def update_status(self, status: str) -> None:
        if status == "SUCCESS":
            self.status = status

    @workflow.signal
    async def payout_started(self, payout_id: str) -> None:
        self._set_payout_status(payout_id, PayoutStatus.STARTED)

    @workflow.signal
    async def payout_completed(self, payout_id: str) -> None:
        self._set_payout_status(payout_id, PayoutStatus.COMPLETED)

    def _set_payout_status(self, payout_id: str, status: PayoutStatus) -> None:
        if payout_id != self._expected_payout_id or self.payout_status == PayoutStatus.COMPLETED:
            return
        if status == PayoutStatus.COMPLETED and self.payout_id != payout_id:
            return
        self.payout_id = payout_id
        self.payout_status = status

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

        info = workflow.info()
        payout_request = OrderPayout(
            name=request.user_id,
            order_workflow_id=info.workflow_id,
            order_run_id=info.run_id,
            order_id=request.order_id,
            order_collection=request.collection,
        )
        self._expected_payout_id = payout_request.payout_workflow_id
        payout = workflow.create_nexus_client(
            endpoint=PAYOUT_NEXUS, service=PayoutService
        )
        await payout.execute_operation(
            PayoutService.run_payout,
            payout_request,
            schedule_to_close_timeout=timedelta(minutes=2),
        )

        if self.payout_status != PayoutStatus.COMPLETED:
            raise ApplicationError("Payout completed without a completion signal")

        return await workflow.execute_activity(
            order.complete,
            args=[request.order_id, request.collection],
            start_to_close_timeout=timedelta(seconds=30),
        )
