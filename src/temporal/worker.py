import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

from src.temporal.activities.greeting import compose_greeting
from src.temporal.activities.hello import print_hello
from src.temporal.activities.order import complete_order
from src.temporal.activities.order_cleanup import delete_order
from src.temporal.workflows.greeting import GreetingWorkflow
from src.temporal.workflows.hello import HelloWorkflow
from src.temporal.workflows.order import OrderWorkflow
from src.temporal.workflows.order_cleanup import OrderCleanupWorkflow


TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "127.0.0.1:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
TEMPORAL_TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "utility-api")


async def main() -> None:
    client = await Client.connect(
        TEMPORAL_ADDRESS,
        namespace=TEMPORAL_NAMESPACE,
    )
    worker = Worker(
        client,
        task_queue=TEMPORAL_TASK_QUEUE,
        workflows=[GreetingWorkflow, HelloWorkflow, OrderWorkflow, OrderCleanupWorkflow],
        activities=[complete_order, compose_greeting, delete_order, print_hello],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
