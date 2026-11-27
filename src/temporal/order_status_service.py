"""Deliver payout status signals to an order through Nexus."""

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from nexusrpc.handler import StartOperationContext, service_handler, sync_operation
from temporalio.client import Client


class PayoutStatus(StrEnum):
    STARTED = "PAYOUT_STARTED"
    COMPLETED = "PAYOUT_COMPLETED"


@dataclass
class OrderPayoutStatus:
    order_workflow_id: str
    order_run_id: str
    payout_id: str
    status: PayoutStatus


@service_handler(name="order_status_service")
class OrderStatusService:
    def __init__(self, client: Client) -> None:
        self._client = client

    @sync_operation
    async def signal_payout_status(
        self, context: StartOperationContext, request: OrderPayoutStatus
    ) -> bool:
        from src.temporal.workflows.order import OrderWorkflow

        handle = self._client.get_workflow_handle(
            request.order_workflow_id, run_id=request.order_run_id
        )
        signal = (
            OrderWorkflow.payout_started
            if request.status == PayoutStatus.STARTED
            else OrderWorkflow.payout_completed
        )
        await handle.signal(signal, request.payout_id, rpc_timeout=timedelta(seconds=5))
        return True
