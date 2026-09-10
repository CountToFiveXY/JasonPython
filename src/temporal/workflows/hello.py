from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.temporal.activities.hello import print_hello


@workflow.defn
class HelloWorkflow:
    @workflow.run
    async def run(self) -> str:
        return await workflow.execute_activity(
            print_hello,
            start_to_close_timeout=timedelta(seconds=10),
        )
