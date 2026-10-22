"""Gauntlet map, track, and lap-time HTTP endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from src.dependencies import get_gauntlet_service
from src.schemas import (
    CarListResponse,
    CarPath,
    CarSummaryResponse,
    Identifier,
    LapTimeRequest,
    MapCreateRequest,
    MapGauntletResponse,
    MapListResponse,
    MapSummaryResponse,
    TrackListResponse,
    TrackLookupRequest,
    TrackLookupResponse,
    TrackGauntletResponse,
    map_gauntlet,
    map_track,
    map_track_gauntlet,
    track_gauntlet,
)
from src.services import GauntletService
from src.services.gauntlet import (
    InvalidNameError,
    LapTimeNotFoundError,
    MapAlreadyExistsError,
    MapNotFoundError,
    TrackNotFoundError,
)


router = APIRouter(prefix="/v1/gauntlet", tags=["Gauntlet"])


@router.get("/maps", response_model=MapListResponse)
async def list_maps(
    service: GauntletService = Depends(get_gauntlet_service),
) -> MapListResponse:
    maps = await service.list_maps()
    return MapListResponse(
        maps=[
            MapSummaryResponse(
                id=game_map.id,
                name=game_map.name,
                chinese_name=game_map.chinese_name,
            )
            for game_map in maps
        ]
    )


@router.get("/cars", response_model=CarListResponse)
async def list_cars(
    service: GauntletService = Depends(get_gauntlet_service),
) -> CarListResponse:
    cars = await service.list_cars()
    return CarListResponse(
        cars=[CarSummaryResponse(id=car.id, name=car.name) for car in cars]
    )


@router.post(
    "/maps",
    response_model=MapGauntletResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_map(
    request: MapCreateRequest,
    service: GauntletService = Depends(get_gauntlet_service),
) -> MapGauntletResponse:
    try:
        game_map = await service.create_map(request.name, request.tracks)
    except InvalidNameError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except MapAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return map_gauntlet(game_map, {})


@router.get("/tracks", response_model=TrackListResponse)
async def list_tracks(
    service: GauntletService = Depends(get_gauntlet_service),
) -> TrackListResponse:
    """Every track with the map it belongs to, for a track selector."""

    return TrackListResponse(
        tracks=[map_track(entry) for entry in await service.list_tracks()]
    )


@router.post("/tracks/lookup", response_model=TrackLookupResponse)
async def lookup_tracks(
    request: TrackLookupRequest,
    service: GauntletService = Depends(get_gauntlet_service),
) -> TrackLookupResponse:
    """Leaderboards for a list of track names, whatever maps they belong to."""

    result = await service.lookup_tracks(request.names)
    return TrackLookupResponse(
        tracks=[map_track_gauntlet(entry) for entry in result.tracks],
        unmatched=result.unmatched,
    )


@router.get("/maps/{map_id}", response_model=MapGauntletResponse)
async def read_map(
    map_id: Identifier,
    service: GauntletService = Depends(get_gauntlet_service),
) -> MapGauntletResponse:
    try:
        result = await service.map_times(map_id)
    except MapNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return map_gauntlet(result.game_map, result.times)


@router.put(
    "/maps/{map_id}/tracks/{track_id}/times",
    response_model=TrackGauntletResponse,
)
async def record_lap_time(
    map_id: Identifier,
    track_id: Identifier,
    request: LapTimeRequest,
    service: GauntletService = Depends(get_gauntlet_service),
) -> TrackGauntletResponse:
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
    return track_gauntlet(result.track, result.times)


@router.delete(
    "/maps/{map_id}/tracks/{track_id}/times/{car}",
    response_model=TrackGauntletResponse,
)
async def delete_lap_time(
    map_id: Identifier,
    track_id: Identifier,
    car: CarPath,
    service: GauntletService = Depends(get_gauntlet_service),
) -> TrackGauntletResponse:
    try:
        result = await service.delete_lap_time(map_id, track_id, car)
    except InvalidNameError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (MapNotFoundError, TrackNotFoundError, LapTimeNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return track_gauntlet(result.track, result.times)
