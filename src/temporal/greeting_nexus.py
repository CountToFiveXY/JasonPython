"""Expose the payout greeting workflow as an asynchronous Nexus operation."""

from dataclasses import dataclass
from datetime import timedelta

from nexusrpc.handler import service_handler
from temporalio import nexus
from temporalio.common import WorkflowIDReusePolicy


@dataclass
class OrderGreeting:
    workflow_id: str
    name: str


@service_handler
class GreetingService:
    @nexus.workflow_run_operation
    async def greet(
        self, context: nexus.WorkflowRunOperationContext, request: OrderGreeting
    ) -> nexus.WorkflowHandle[str]:
        from src.temporal.workflows.payout import PayoutWorkflow

        return await context.start_workflow(
            PayoutWorkflow.run,
            request.name,
            id=request.workflow_id,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            execution_timeout=timedelta(minutes=2),
        )
