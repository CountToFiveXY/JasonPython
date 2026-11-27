"""Order creation use case."""

import asyncio
from datetime import datetime, timedelta, timezone
import os
from uuid import uuid4

from temporalio.client import Client as TemporalClient

from src.entity import Order, OrderStatus
from src.temporal.activities.firestore import firestore_client
from src.temporal.config import TEMPORAL_ORDER_TASK_QUEUE
from src.temporal.workflows.order import OrderWorkflow, OrderWorkflowInput


ORDER_COLLECTION = os.getenv("FIRESTORE_ORDER_COLLECTION", "orders")


class OrderService:
    """Creates orders and starts their Temporal workflows."""

    def __init__(self, temporal_client: TemporalClient) -> None:
        self._temporal_client = temporal_client

    async def create(self, user_id: str) -> Order:
        order_id = str(uuid4())
        created = datetime.now(timezone.utc)
        order = Order(
            id=order_id,
            user_id=user_id,
            created=created,
            expires_at=created + timedelta(days=1),
            status=OrderStatus.STARTED,
        )

        document = firestore_client().collection(ORDER_COLLECTION).document(order.id)
        await asyncio.to_thread(
            document.create,
            order.model_dump() | {"status": order.status.value},
        )

        await self._temporal_client.start_workflow(
            OrderWorkflow.run,
            OrderWorkflowInput(
                order_id=order.id,
                user_id=order.user_id,
                created=order.created.isoformat(),
                expires_at=order.expires_at.isoformat(),
                status=order.status.value,
                collection=ORDER_COLLECTION,
            ),
            id=order.id,
            task_queue=TEMPORAL_ORDER_TASK_QUEUE,
        )
        return order
