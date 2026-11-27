"""Start payouts through Nexus and report lifecycle changes to orders."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

from google.api_core.exceptions import AlreadyExists
from google.cloud import firestore
from nexusrpc.handler import service_handler
from temporalio import activity, nexus
from temporalio.common import WorkflowIDReusePolicy

from src.temporal.activities.firestore import firestore_client
from src.temporal.activities.payout import compose_payout_result

if TYPE_CHECKING:
    from src.services.order import OrderService


@dataclass
class OrderPayout:
    name: str
    order_workflow_id: str
    order_run_id: str
    order_id: str | None = None
    order_collection: str = "orders"

    @property
    def payout_workflow_id(self) -> str:
        if self.order_id:
            return f"{self.order_id}_payout"
        return f"order-payout-{self.order_run_id}"


class PayoutStatus(StrEnum):
    STARTED = "PAYOUT_STARTED"
    COMPLETED = "PAYOUT_COMPLETED"


def _create_payout_document(request: OrderPayout) -> None:
    payout_id = request.payout_workflow_id
    order_id = request.order_id or request.order_workflow_id
    document = firestore_client().collection("payouts").document(payout_id)
    try:
        document.create({"id": payout_id, "order_id": order_id, "status": "INITIATED"})
    except AlreadyExists:
        fields = document.get().to_dict()
        if fields is None or fields.get("order_id") != order_id:
            raise ValueError(f"Payout {payout_id} belongs to another order") from None


def _persist_payout_status(transaction, payout_document, status: PayoutStatus) -> None:
    payout_fields = payout_document.get(transaction=transaction).to_dict()
    if payout_fields is None:
        raise ValueError(f"Payout {payout_document.id} does not exist")
    if payout_fields.get("status") == PayoutStatus.COMPLETED.name:
        return
    transaction.update(payout_document, {"status": status.name})


def _write_payout_status(payout_id: str, status: PayoutStatus) -> None:
    client = firestore_client()
    document = client.collection("payouts").document(payout_id)
    firestore.transactional(_persist_payout_status)(client.transaction(), document, status)


@service_handler(name="payout_service")
class PayoutService:
    def __init__(self, order_service: "OrderService") -> None:
        self._order_service = order_service

    @nexus.workflow_run_operation
    async def run_payout(
        self, context: nexus.WorkflowRunOperationContext, request: OrderPayout
    ) -> nexus.WorkflowHandle[str]:
        from src.temporal.workflows.payout import PayoutWorkflow

        await asyncio.to_thread(_create_payout_document, request)
        return await context.start_workflow(
            PayoutWorkflow.run,
            request,
            id=request.payout_workflow_id,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            execution_timeout=timedelta(minutes=2),
        )

    @activity.defn(name="payout.start")
    async def start(self, request: OrderPayout) -> str:
        await self._update_status_and_notify_order(request, PayoutStatus.STARTED)
        return await compose_payout_result(request.name)

    @activity.defn(name="payout.complete")
    async def complete(self, request: OrderPayout) -> None:
        await self._update_status_and_notify_order(request, PayoutStatus.COMPLETED)

    async def _update_status_and_notify_order(self, request: OrderPayout, status: PayoutStatus) -> None:
        payout_id = activity.info().workflow_id
        await asyncio.to_thread(_write_payout_status, payout_id, status)
        await self._order_service.receive_payout_status(request, payout_id, status)
