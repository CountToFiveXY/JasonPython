"""Galaxy Lens leaderboard HTTP endpoint."""

from fastapi import APIRouter, Depends, HTTPException, status

from src.dependencies import get_leaderboard_service
from src.schemas import LeaderboardListResponse
from src.services import LeaderboardService
from src.services.leaderboard import LeaderboardError


router = APIRouter(prefix="/v1/leaderboard", tags=["Leaderboard"])


@router.get("", response_model=LeaderboardListResponse)
def list_leaderboards(
    service: LeaderboardService = Depends(get_leaderboard_service),
) -> LeaderboardListResponse:
    try:
        leaderboards = service.fetch()
    except LeaderboardError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return LeaderboardListResponse(
        source="https://al.galaxylens.de/leaderboards",
        leaderboards=leaderboards,
    )
