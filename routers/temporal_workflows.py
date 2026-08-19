import os
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from temporalio.client import Client

from database import get_temporal
from temporal_service.workflows import GreetingWorkflow


router = APIRouter(prefix="/workflows", tags=["Temporal Workflows"])
TEMPORAL_TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "utility-api")


class GreetingRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class GreetingResponse(BaseModel):
    workflow_id: str
    result: str


@router.post("/greeting", response_model=GreetingResponse)
async def run_greeting(
    request: GreetingRequest,
    temporal_client: Client = Depends(get_temporal),
) -> GreetingResponse:
    workflow_id = f"greeting-{uuid4()}"
    result = await temporal_client.execute_workflow(
        GreetingWorkflow.run,
        request.name,
        id=workflow_id,
        task_queue=TEMPORAL_TASK_QUEUE,
    )
    return GreetingResponse(workflow_id=workflow_id, result=result)
