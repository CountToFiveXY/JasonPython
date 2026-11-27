import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from src.services.order import OrderService
from src.temporal.activities import order
from src.temporal.activities.payout import compose_payout_result
from src.temporal.activities.hello import print_hello
from src.temporal.config import (
    TEMPORAL_ADDRESS,
    TEMPORAL_NAMESPACE,
    TEMPORAL_ORDER_NAMESPACE,
    TEMPORAL_ORDER_TASK_QUEUE,
    TEMPORAL_PAYOUT_NAMESPACE,
    TEMPORAL_PAYOUT_TASK_QUEUE,
    TEMPORAL_TASK_QUEUE,
)
from src.temporal.payout_service import PayoutService
from src.temporal.workflows.payout import PayoutWorkflow
from src.temporal.workflows.hello import HelloWorkflow
from src.temporal.workflows.order import OrderWorkflow


async def main() -> None:
    hello_client, order_client, payout_client = await asyncio.gather(
        Client.connect(TEMPORAL_ADDRESS, namespace=TEMPORAL_NAMESPACE),
        Client.connect(TEMPORAL_ADDRESS, namespace=TEMPORAL_ORDER_NAMESPACE),
        Client.connect(TEMPORAL_ADDRESS, namespace=TEMPORAL_PAYOUT_NAMESPACE),
    )
    payout_service = PayoutService(OrderService(order_client))
    workers = (
        Worker(
            hello_client,
            task_queue=TEMPORAL_TASK_QUEUE,
            workflows=[HelloWorkflow],
            activities=[print_hello],
        ),
        Worker(
            order_client,
            task_queue=TEMPORAL_ORDER_TASK_QUEUE,
            workflows=[OrderWorkflow],
            activities=[order.complete],
        ),
        Worker(
            payout_client,
            task_queue=TEMPORAL_PAYOUT_TASK_QUEUE,
            workflows=[PayoutWorkflow],
            activities=[compose_payout_result, payout_service.start, payout_service.complete],
            nexus_service_handlers=[payout_service],
        ),
    )

    async with asyncio.TaskGroup() as tasks:
        for worker in workers:
            tasks.create_task(worker.run())


if __name__ == "__main__":
    asyncio.run(main())
