"""Create orders and handle payout notifications."""

import asyncio
from datetime import datetime, timedelta, timezone
import os
from uuid import uuid4

from google.cloud import firestore
from temporalio.client import Client as TemporalClient

from src.entity import Order, OrderStatus
from src.temporal.activities.firestore import WORKFLOW_DOCUMENT_LIFETIME, firestore_client
from src.temporal.config import TEMPORAL_ORDER_TASK_QUEUE
from src.temporal.payout_service import OrderPayout, PayoutStatus
from src.temporal.workflows.order import OrderWorkflow, OrderWorkflowInput


ORDER_COLLECTION = os.getenv("FIRESTORE_ORDER_COLLECTION", "orders")


def _persist_order_payout(transaction, document, payout_id: str, status: PayoutStatus) -> None:
    fields = document.get(transaction=transaction).to_dict()
    if fields is None:
        raise ValueError(f"Order {document.id} does not exist")
    saved_id = fields.get("payout_id")
    if saved_id is not None and saved_id != payout_id:
        raise ValueError(f"Order belongs to another payout: {saved_id}")
    if fields.get("payout_status") == PayoutStatus.COMPLETED:
        return
    transaction.update(document, {"payout_id": payout_id, "payout_status": status.value})


def _write_order_payout(request: OrderPayout, payout_id: str, status: PayoutStatus) -> None:
    client = firestore_client()
    document = client.collection(request.order_collection).document(
        request.order_id or request.order_workflow_id
    )
    firestore.transactional(_persist_order_payout)(client.transaction(), document, payout_id, status)


class OrderService:
    """Owns order creation and payout status updates."""

    def __init__(self, temporal_client: TemporalClient) -> None:
        self._temporal_client = temporal_client

    async def create(self, user_id: str) -> Order:
        order_id = str(uuid4())
        created = datetime.now(timezone.utc)
        order = Order(
            id=order_id,
            user_id=user_id,
            created=created,
            expires_at=created + WORKFLOW_DOCUMENT_LIFETIME,
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

    async def receive_payout_status(
        self, request: OrderPayout, payout_id: str, status: PayoutStatus
    ) -> None:
        if payout_id != request.payout_workflow_id:
            raise ValueError(f"Unexpected payout workflow ID: {payout_id}")
        handle = self._temporal_client.get_workflow_handle(
            request.order_workflow_id, run_id=request.order_run_id
        )
        signal = (
            OrderWorkflow.payout_started
            if status == PayoutStatus.STARTED
            else OrderWorkflow.payout_completed
        )
        await handle.signal(signal, payout_id, rpc_timeout=timedelta(seconds=5))
        await asyncio.to_thread(_write_order_payout, request, payout_id, status)
