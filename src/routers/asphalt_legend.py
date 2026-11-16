"""Endpoints that send one-shot tasks to the Asphalt Legend Windows worker."""

from fastapi import APIRouter, Depends, HTTPException, status

from src.dependencies import get_asphalt_legend_service
from src.schemas.asphalt_legend import (
    AsphaltLegendTaskRequest,
    AsphaltLegendTaskResponse,
)
from src.services.asphalt_legend import AsphaltLegendPublishError, AsphaltLegendService


router = APIRouter(prefix="/v1/asphalt-legend/tasks", tags=["Asphalt Legend"])


@router.post(
    "",
    response_model=AsphaltLegendTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def publish_task(
    request: AsphaltLegendTaskRequest,
    service: AsphaltLegendService = Depends(get_asphalt_legend_service),
) -> AsphaltLegendTaskResponse:
    try:
        published = await service.publish(request.type)
    except AsphaltLegendPublishError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return AsphaltLegendTaskResponse(
        type=published.type,
        topic=published.topic,
        message_id=published.message_id,
    )
