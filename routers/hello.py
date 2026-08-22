import os
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from temporalio.client import Client

from database import get_temporal
from temporal_service.workflows import HelloWorkflow


router = APIRouter(prefix="/workflows", tags=["Temporal Workflows"])
TEMPORAL_TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "utility-api")


class WorkflowResponse(BaseModel):
    workflow_id: str
    result: str


@router.post("/hello", response_model=WorkflowResponse)
async def run_hello(
    temporal_client: Client = Depends(get_temporal),
) -> WorkflowResponse:
    workflow_id = f"hello-{uuid4()}"
    result = await temporal_client.execute_workflow(
        HelloWorkflow.run,
        id=workflow_id,
        task_queue=TEMPORAL_TASK_QUEUE,
    )
    return WorkflowResponse(workflow_id=workflow_id, result=result)
