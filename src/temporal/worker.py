import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

from src.temporal.activities import order
from src.temporal.activities.payout import compose_payout_result
from src.temporal.activities.hello import print_hello
from src.temporal.config import (
    TEMPORAL_ADDRESS,
    TEMPORAL_NAMESPACE,
    TEMPORAL_ORDER_NAMESPACE,
    TEMPORAL_PAYOUT_NAMESPACE,
)
from src.temporal.payout_service import PayoutService
from src.temporal.workflows.payout import PayoutWorkflow
from src.temporal.workflows.hello import HelloWorkflow
from src.temporal.workflows.order import OrderWorkflow


TEMPORAL_TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "utility-api")


async def main() -> None:
    registrations = (
        (TEMPORAL_NAMESPACE, HelloWorkflow, [print_hello], []),
        (TEMPORAL_ORDER_NAMESPACE, OrderWorkflow, [order.create, order.complete], []),
        (TEMPORAL_PAYOUT_NAMESPACE, PayoutWorkflow, [compose_payout_result], [PayoutService()]),
    )
    workers = []
    for namespace, workflow_type, activities, nexus_handlers in registrations:
        client = await Client.connect(TEMPORAL_ADDRESS, namespace=namespace)
        workers.append(
            Worker(
                client,
                task_queue=TEMPORAL_TASK_QUEUE,
                workflows=[workflow_type],
                activities=activities,
                nexus_service_handlers=nexus_handlers,
            )
        )

    async with asyncio.TaskGroup() as tasks:
        for worker in workers:
            tasks.create_task(worker.run())


if __name__ == "__main__":
    asyncio.run(main())
