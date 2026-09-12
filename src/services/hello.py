"""Hello workflow use case."""

import os
from dataclasses import dataclass
from uuid import uuid4

from temporalio.client import Client as TemporalClient

from src.temporal.workflows.hello import HelloWorkflow


TEMPORAL_TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "utility-api")


@dataclass(frozen=True)
class WorkflowExecution:
    workflow_id: str
    result: str


class HelloService:
    def __init__(self, temporal_client: TemporalClient) -> None:
        self._temporal_client = temporal_client

    async def run(self) -> WorkflowExecution:
        workflow_id = f"hello-{uuid4()}"
        result = await self._temporal_client.execute_workflow(
            HelloWorkflow.run,
            id=workflow_id,
            task_queue=TEMPORAL_TASK_QUEUE,
        )
        return WorkflowExecution(workflow_id=workflow_id, result=result)
