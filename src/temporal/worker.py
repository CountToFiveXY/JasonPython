import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

from src.temporal.activities.firestore import write_firestore_document
from src.temporal.activities.greeting import compose_greeting
from src.temporal.activities.hello import print_hello
from src.temporal.activities.order import complete_order
from src.temporal.config import (
    TEMPORAL_ADDRESS,
    TEMPORAL_NAMESPACE,
    TEMPORAL_ORDER_NAMESPACE,
    TEMPORAL_PAYOUT_NAMESPACE,
)
from src.temporal.workflows.greeting import GreetingWorkflow
from src.temporal.workflows.hello import HelloWorkflow
from src.temporal.workflows.order import OrderWorkflow


TEMPORAL_TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "utility-api")


async def main() -> None:
    registrations = (
        (TEMPORAL_NAMESPACE, HelloWorkflow, [print_hello]),
        (TEMPORAL_ORDER_NAMESPACE, OrderWorkflow, [complete_order, write_firestore_document]),
        (TEMPORAL_PAYOUT_NAMESPACE, GreetingWorkflow, [compose_greeting]),
    )
    workers = []
    for namespace, workflow_type, activities in registrations:
        client = await Client.connect(TEMPORAL_ADDRESS, namespace=namespace)
        workers.append(
            Worker(
                client,
                task_queue=TEMPORAL_TASK_QUEUE,
                workflows=[workflow_type],
                activities=activities,
            )
        )

    async with asyncio.TaskGroup() as tasks:
        for worker in workers:
            tasks.create_task(worker.run())


if __name__ == "__main__":
    asyncio.run(main())
