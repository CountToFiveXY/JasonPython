from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.temporal.activities.order_cleanup import delete_order


@workflow.defn
class OrderCleanupWorkflow:
    @workflow.run
    async def run(self, order_id: str) -> str:
        await workflow.sleep(timedelta(days=1))
        return await workflow.execute_activity(
            delete_order,
            order_id,
            start_to_close_timeout=timedelta(seconds=30),
        )
