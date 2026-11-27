from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.temporal.activities.payout import compose_payout_result
    from src.temporal.payout_service import OrderPayout, PayoutService


@workflow.defn
class PayoutWorkflow:
    @workflow.run
    async def run(self, request: OrderPayout | str) -> str:
        if isinstance(request, str):
            return await workflow.execute_activity(
                compose_payout_result,
                request,
                start_to_close_timeout=timedelta(seconds=10),
            )

        result = await workflow.execute_activity_method(
            PayoutService.start,
            request,
            start_to_close_timeout=timedelta(seconds=10),
            schedule_to_close_timeout=timedelta(seconds=45),
        )
        await workflow.execute_activity_method(
            PayoutService.complete,
            request,
            start_to_close_timeout=timedelta(seconds=10),
            schedule_to_close_timeout=timedelta(seconds=45),
        )
        return result
