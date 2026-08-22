import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

from temporal.activities import compose_greeting, print_hello
from temporal.workflows import GreetingWorkflow, HelloWorkflow


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
        workflows=[GreetingWorkflow, HelloWorkflow],
        activities=[compose_greeting, print_hello],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
