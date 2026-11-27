"""Endpoints that send Asphalt tasks and expose refill status."""

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from google.api_core.exceptions import GoogleAPICallError
from google.cloud.firestore_v1 import Client

from src.dependencies import get_asphalt_task_service
from src.infrastructure.clients import get_firestore
from src.repositories.asphalt_tasks import AsphaltTasks
from src.schemas.asphalt_tasks import (
    AsphaltTaskRequest,
    AsphaltTaskHistoryEntry,
    AsphaltTaskResponse,
    AsphaltTaskSnapshot,
)
from src.services.asphalt_tasks import AsphaltTaskPublishError, AsphaltTaskService


router = APIRouter(prefix="/v1/asphalt-tasks", tags=["Asphalt Tasks"])


@router.post(
    "",
    response_model=AsphaltTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    response_model_exclude_none=True,
)
async def publish_task(
    request: AsphaltTaskRequest,
    service: AsphaltTaskService = Depends(get_asphalt_task_service),
) -> AsphaltTaskResponse:
    try:
        published = await service.publish(
            request.type, request.repeat, track_completion=request.track_completion
        )
    except AsphaltTaskPublishError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return AsphaltTaskResponse(
        type=published.type,
        repeat=published.repeat,
        topic=published.topic,
        message_id=published.message_id,
        task_id=published.task_id,
    )


@router.get("", response_model_exclude_none=True)
async def recent_tasks(client: Client = Depends(get_firestore)) -> list[AsphaltTaskHistoryEntry]:
    try:
        return await asyncio.to_thread(AsphaltTasks(client).recent)
    except GoogleAPICallError as exc:
        raise HTTPException(status_code=503, detail="Task history is unavailable.") from exc


@router.get("/{task_id}", response_model_exclude_none=True)
async def refill_status(
    task_id: UUID, client: Client = Depends(get_firestore)
) -> AsphaltTaskSnapshot:
    try:
        result = await asyncio.to_thread(AsphaltTasks(client).get, task_id)
    except GoogleAPICallError as exc:
        raise HTTPException(status_code=503, detail="Refill status is unavailable.") from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Refill task not found.")
    return result
