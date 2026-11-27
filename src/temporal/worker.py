import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

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
from src.temporal.order_status_service import OrderStatusService
from src.temporal.payout_service import PayoutService
from src.temporal.workflows.payout import PayoutWorkflow
from src.temporal.workflows.hello import HelloWorkflow
from src.temporal.workflows.order import OrderWorkflow


async def main() -> None:
    registrations = (
        (TEMPORAL_NAMESPACE, TEMPORAL_TASK_QUEUE, HelloWorkflow, [print_hello], []),
        (
            TEMPORAL_ORDER_NAMESPACE, TEMPORAL_ORDER_TASK_QUEUE,
            OrderWorkflow, [order.create, order.record_payout, order.complete], [],
        ),
        (
            TEMPORAL_PAYOUT_NAMESPACE, TEMPORAL_PAYOUT_TASK_QUEUE,
            PayoutWorkflow, [compose_payout_result], [PayoutService()],
        ),
    )
    workers = []
    for namespace, task_queue, workflow_type, activities, nexus_handlers in registrations:
        client = await Client.connect(TEMPORAL_ADDRESS, namespace=namespace)
        if workflow_type is OrderWorkflow:
            nexus_handlers = [OrderStatusService(client)]
        workers.append(
            Worker(
                client,
                task_queue=task_queue,
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
