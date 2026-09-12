"""Hello workflow HTTP endpoint."""

from fastapi import APIRouter, Depends

from src.dependencies import get_hello_service
from src.schemas import WorkflowResponse
from src.services import HelloService


router = APIRouter(prefix="/workflows", tags=["Temporal Workflows"])


@router.post("/hello", response_model=WorkflowResponse)
async def run_hello(
    service: HelloService = Depends(get_hello_service),
) -> WorkflowResponse:
    execution = await service.run()
    return WorkflowResponse(
        workflow_id=execution.workflow_id,
        result=execution.result,
    )
