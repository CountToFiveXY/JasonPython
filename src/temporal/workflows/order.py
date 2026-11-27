import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.exceptions import ApplicationError

with workflow.unsafe.imports_passed_through():
    from src.temporal.activities import order
    from src.temporal.activities.order import OrderWorkflowInput
    from src.temporal.config import PAYOUT_NEXUS
    from src.temporal.order_status_service import PayoutStatus
    from src.temporal.payout_service import PayoutService, OrderPayout


@workflow.defn
class OrderWorkflow:
    def __init__(self) -> None:
        self.status: str | None = None
        self.payout_id: str | None = None
        self.payout_status: PayoutStatus | None = None
        self._expected_payout_id: str | None = None
        self._request: OrderWorkflowInput | None = None
        self._payout_status_lock = asyncio.Lock()

    @workflow.signal
    async def update_status(self, status: str) -> None:
        if status == "SUCCESS":
            self.status = status

    @workflow.signal
    async def payout_started(self, payout_id: str) -> None:
        await self._record_payout_status(payout_id, PayoutStatus.STARTED)

    @workflow.signal
    async def payout_completed(self, payout_id: str) -> None:
        await self._record_payout_status(payout_id, PayoutStatus.COMPLETED)

    async def _record_payout_status(self, payout_id: str, status: PayoutStatus) -> None:
        async with self._payout_status_lock:
            request = self._request
            if request is None or payout_id != self._expected_payout_id:
                return
            if self.payout_status in (status, PayoutStatus.COMPLETED):
                return
            if status == PayoutStatus.COMPLETED and self.payout_id != payout_id:
                return
            await workflow.execute_activity(
                order.record_payout,
                args=[request.order_id, request.collection, payout_id, status.value],
                start_to_close_timeout=timedelta(seconds=30),
                schedule_to_close_timeout=timedelta(minutes=2),
            )
            self.payout_id = payout_id
            self.payout_status = status

    @workflow.run
    async def run(self, request: OrderWorkflowInput) -> str:
        self._request = request
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
        payout_id = f"order-payout-{info.run_id}"
        self._expected_payout_id = payout_id
        payout = workflow.create_nexus_client(
            endpoint=PAYOUT_NEXUS, service=PayoutService
        )
        await payout.execute_operation(
            PayoutService.run_payout,
            OrderPayout(
                workflow_id=payout_id,
                name=request.user_id,
                order_workflow_id=info.workflow_id,
                order_run_id=info.run_id,
            ),
            schedule_to_close_timeout=timedelta(minutes=2),
        )

        await workflow.wait_condition(workflow.all_handlers_finished)
        if self.payout_status != PayoutStatus.COMPLETED:
            raise ApplicationError("Payout completed without a completion signal")

        return await workflow.execute_activity(
            order.complete,
            args=[request.order_id, request.collection],
            start_to_close_timeout=timedelta(seconds=30),
        )
