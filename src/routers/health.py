"""Health-check HTTP endpoint."""

from fastapi import APIRouter, Depends, HTTPException

from src.dependencies import get_health_service
from src.schemas import HealthResponse
from src.services import HealthService
from src.services.health import RedisUnavailableError


router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=HealthResponse)
async def health_check(
    service: HealthService = Depends(get_health_service),
) -> HealthResponse:
    try:
        result = await service.check()
    except RedisUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return HealthResponse(**result)
