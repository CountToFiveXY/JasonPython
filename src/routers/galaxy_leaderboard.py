"""Galaxy Lens leaderboard HTTP endpoint."""

from fastapi import APIRouter, Depends, HTTPException, status

from src.dependencies import get_galaxy_leaderboard_service
from src.schemas import GalaxyLeaderboardListResponse
from src.services import GalaxyLeaderboardService
from src.services.galaxy_leaderboards import GalaxyLeaderboardError


router = APIRouter(prefix="/v1/leaderboard", tags=["Leaderboard"])


@router.get("", response_model=GalaxyLeaderboardListResponse)
def list_galaxy_leaderboards(
    service: GalaxyLeaderboardService = Depends(get_galaxy_leaderboard_service),
) -> GalaxyLeaderboardListResponse:
    try:
        leaderboards = service.fetch()
    except GalaxyLeaderboardError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return GalaxyLeaderboardListResponse(
        source="https://al.galaxylens.de/leaderboards",
        leaderboards=leaderboards,
    )
