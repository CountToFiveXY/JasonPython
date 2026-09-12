"""Map, track, and lap-time HTTP endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from src.dependencies import get_leaderboard_service
from src.schemas import (
    CarListResponse,
    CarPath,
    CarSummaryResponse,
    Identifier,
    LapTimeRequest,
    MapCreateRequest,
    MapLeaderboardResponse,
    MapListResponse,
    MapSummaryResponse,
    TrackLeaderboardResponse,
    map_leaderboard,
    track_leaderboard,
)
from src.services import LeaderboardService
from src.services.leaderboard import (
    InvalidNameError,
    LapTimeNotFoundError,
    MapAlreadyExistsError,
    MapNotFoundError,
    TrackNotFoundError,
)


router = APIRouter(prefix="/v1/leaderboard", tags=["Leaderboard"])


@router.get("/maps", response_model=MapListResponse)
async def list_maps(
    service: LeaderboardService = Depends(get_leaderboard_service),
) -> MapListResponse:
    maps = await service.list_maps()
    return MapListResponse(
        maps=[MapSummaryResponse(id=game_map.id, name=game_map.name) for game_map in maps]
    )


@router.get("/cars", response_model=CarListResponse)
async def list_cars(
    service: LeaderboardService = Depends(get_leaderboard_service),
) -> CarListResponse:
    cars = await service.list_cars()
    return CarListResponse(
        cars=[CarSummaryResponse(id=car.id, name=car.name) for car in cars]
    )


@router.post(
    "/maps",
    response_model=MapLeaderboardResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_map(
    request: MapCreateRequest,
    service: LeaderboardService = Depends(get_leaderboard_service),
) -> MapLeaderboardResponse:
    try:
        game_map = await service.create_map(request.name, request.tracks)
    except InvalidNameError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except MapAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return map_leaderboard(game_map, {})


@router.get("/maps/{map_id}", response_model=MapLeaderboardResponse)
async def read_map(
    map_id: Identifier,
    service: LeaderboardService = Depends(get_leaderboard_service),
) -> MapLeaderboardResponse:
    try:
        result = await service.map_times(map_id)
    except MapNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return map_leaderboard(result.game_map, result.times)


@router.put(
    "/maps/{map_id}/tracks/{track_id}/times",
    response_model=TrackLeaderboardResponse,
)
async def record_lap_time(
    map_id: Identifier,
    track_id: Identifier,
    request: LapTimeRequest,
    service: LeaderboardService = Depends(get_leaderboard_service),
) -> TrackLeaderboardResponse:
    try:
        result = await service.record_lap_time(
            map_id,
            track_id,
            request.car,
            request.seconds,
        )
    except InvalidNameError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (MapNotFoundError, TrackNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return track_leaderboard(result.track, result.times)


@router.delete(
    "/maps/{map_id}/tracks/{track_id}/times/{car}",
    response_model=TrackLeaderboardResponse,
)
async def delete_lap_time(
    map_id: Identifier,
    track_id: Identifier,
    car: CarPath,
    service: LeaderboardService = Depends(get_leaderboard_service),
) -> TrackLeaderboardResponse:
    try:
        result = await service.delete_lap_time(map_id, track_id, car)
    except InvalidNameError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (MapNotFoundError, TrackNotFoundError, LapTimeNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return track_leaderboard(result.track, result.times)
