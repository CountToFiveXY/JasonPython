"""Expose the payout workflow as an asynchronous Nexus operation."""

from dataclasses import dataclass
from datetime import timedelta

from nexusrpc.handler import service_handler
from temporalio import nexus
from temporalio.common import WorkflowIDReusePolicy


@dataclass
class OrderPayout:
    name: str
    order_workflow_id: str
    order_run_id: str
    order_id: str | None = None

    @property
    def payout_workflow_id(self) -> str:
        if self.order_id:
            return f"{self.order_id}_payout"
        return f"order-payout-{self.order_run_id}"


@service_handler(name="payout_service")
class PayoutService:
    @nexus.workflow_run_operation
    async def run_payout(
        self, context: nexus.WorkflowRunOperationContext, request: OrderPayout
    ) -> nexus.WorkflowHandle[str]:
        from src.temporal.workflows.payout import PayoutWorkflow

        return await context.start_workflow(
            PayoutWorkflow.run,
            request,
            id=request.payout_workflow_id,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            execution_timeout=timedelta(minutes=2),
        )
