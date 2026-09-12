"""Ranking image HTTP endpoints."""

from io import BytesIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from src.dependencies import get_ranking_service
from src.schemas import RankingRequest
from src.services import RankingService


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
