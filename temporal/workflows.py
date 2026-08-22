from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from temporal.activities import compose_greeting, print_hello


@workflow.defn
class HelloWorkflow:
    @workflow.run
    async def run(self) -> str:
        return await workflow.execute_activity(
            print_hello,
            start_to_close_timeout=timedelta(seconds=10),
        )


@workflow.defn
class GreetingWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        return await workflow.execute_activity(
            compose_greeting,
            name,
            start_to_close_timeout=timedelta(seconds=10),
        )
