from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.temporal.activities.payout import compose_payout_result
    from src.temporal.config import ORDER_STATUS_NEXUS
    from src.temporal.order_status_service import OrderPayoutStatus, OrderStatusService, PayoutStatus
    from src.temporal.payout_service import OrderPayout


@workflow.defn
class PayoutWorkflow:
    @workflow.run
    async def run(self, request: OrderPayout | str) -> str:
        if isinstance(request, str):
            return await self._compose_result(request)

        order_status = workflow.create_nexus_client(
            endpoint=ORDER_STATUS_NEXUS, service=OrderStatusService
        )
        await self._signal_status(order_status, request, PayoutStatus.STARTED)
        result = await self._compose_result(request.name)
        await self._signal_status(order_status, request, PayoutStatus.COMPLETED)
        return result

    async def _compose_result(self, name: str) -> str:
        return await workflow.execute_activity(
            compose_payout_result,
            name,
            start_to_close_timeout=timedelta(seconds=10),
        )

    async def _signal_status(
        self,
        client: workflow.NexusClient[OrderStatusService],
        request: OrderPayout,
        status: PayoutStatus,
    ) -> None:
        await client.execute_operation(
            OrderStatusService.signal_payout_status,
            OrderPayoutStatus(
                order_workflow_id=request.order_workflow_id,
                order_run_id=request.order_run_id,
                payout_id=workflow.info().workflow_id,
                status=status,
            ),
            schedule_to_close_timeout=timedelta(seconds=30),
        )
