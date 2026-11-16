"""Endpoints that send one-shot tasks to an Asphalt worker."""

from fastapi import APIRouter, Depends, HTTPException, status

from src.dependencies import get_asphalt_task_service
from src.schemas.asphalt_tasks import (
    AsphaltTaskRequest,
    AsphaltTaskResponse,
)
from src.services.asphalt_tasks import AsphaltTaskPublishError, AsphaltTaskService


router = APIRouter(prefix="/v1/asphalt-tasks", tags=["Asphalt Tasks"])


@router.post(
    "",
    response_model=AsphaltTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def publish_task(
    request: AsphaltTaskRequest,
    service: AsphaltTaskService = Depends(get_asphalt_task_service),
) -> AsphaltTaskResponse:
    try:
        published = await service.publish(request.type)
    except AsphaltTaskPublishError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return AsphaltTaskResponse(
        type=published.type,
        topic=published.topic,
        message_id=published.message_id,
    )
