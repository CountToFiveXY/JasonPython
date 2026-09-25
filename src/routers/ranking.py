"""Ranking image HTTP endpoints."""

from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from src.dependencies import get_galaxy_leaderboard_service, get_ranking_service
from src.schemas import (
    GalaxyLeaderboardListResponse,
    RankingRequest,
)
from src.services import GalaxyLeaderboardService, RankingService
from src.services.galaxy_leaderboards import GalaxyLeaderboardError


router = APIRouter(prefix="/v1/ranking", tags=["Images"])


@router.post("", response_class=StreamingResponse)
def create_ranking(
    request: RankingRequest,
    service: RankingService = Depends(get_ranking_service),
) -> StreamingResponse:
    ranking = service.create(request.total, request.type, request.car)
    return StreamingResponse(
        BytesIO(ranking.content),
        media_type="image/png",
        headers={
            "Content-Disposition": f'attachment; filename="{ranking.filename}"'
        },
    )


@router.get("/leaderboards", response_model=GalaxyLeaderboardListResponse)
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
