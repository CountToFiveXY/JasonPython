from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.temporal.activities.payout import compose_payout_result


@workflow.defn
class PayoutWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        return await workflow.execute_activity(
            compose_payout_result,
            name,
            start_to_close_timeout=timedelta(seconds=10),
        )
