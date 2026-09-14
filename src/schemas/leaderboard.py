"""HTTP schemas for the leaderboard API."""

from typing import Annotated

from fastapi import Path
from pydantic import AfterValidator, BaseModel, Field

from src.entity import TRACKS_PER_MAP, GameMap, LapTime, Track


def _collapse_whitespace(value: str) -> str:
    collapsed = " ".join(value.split())
    if not collapsed:
        raise ValueError("must not be blank")
    return collapsed


#: Display names may not contain path separators or control characters, so a
#: name can always be carried in a URL path segment.
_NAME_PATTERN = r"^[^/\\\x00-\x1f]+$"

Name = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=_NAME_PATTERN),
    AfterValidator(_collapse_whitespace),
]
CarName = Annotated[
    str,
    Field(min_length=1, max_length=32, pattern=_NAME_PATTERN),
    AfterValidator(_collapse_whitespace),
]
Seconds = Annotated[float, Field(gt=0, lt=3_600)]


Identifier = Annotated[
    str,
    Path(
        min_length=1,
        max_length=64,
        pattern=r"^[\w-]{1,64}$",
        description="Identifier derived from the display name",
    ),
]
CarPath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=32,
        description="Car name, matched without regard to case or spacing",
    ),
]


class MapCreateRequest(BaseModel):
    """A new map and the names of the tracks that belong to it."""

    name: Name
    tracks: Annotated[
        list[Name],
        Field(min_length=TRACKS_PER_MAP, max_length=TRACKS_PER_MAP),
    ]


class LapTimeRequest(BaseModel):
    """A car's time on a track, replacing any time it already holds there."""

    car: CarName
    seconds: Seconds


class LapTimeEntry(LapTime):
    rank: int


class TrackLeaderboardResponse(Track):
    times: list[LapTimeEntry]


class MapLeaderboardResponse(BaseModel):
    id: str
    name: str
    chinese_name: str = ""
    tracks: list[TrackLeaderboardResponse]


class CarSummaryResponse(BaseModel):
    id: str
    name: str


class CarListResponse(BaseModel):
    cars: list[CarSummaryResponse]


class MapSummaryResponse(BaseModel):
    id: str
    name: str
    chinese_name: str = ""


class MapListResponse(BaseModel):
    maps: list[MapSummaryResponse]


def ranked(times: list[LapTime]) -> list[LapTimeEntry]:
    """Number an already-sorted list of times from one."""

    return [
        LapTimeEntry(rank=position, **lap_time.model_dump())
        for position, lap_time in enumerate(times, start=1)
    ]


def track_leaderboard(track: Track, times: list[LapTime]) -> TrackLeaderboardResponse:
    return TrackLeaderboardResponse(**track.model_dump(), times=ranked(times))


def map_leaderboard(
    game_map: GameMap,
    times: dict[str, list[LapTime]],
) -> MapLeaderboardResponse:
    return MapLeaderboardResponse(
        id=game_map.id,
        name=game_map.name,
        chinese_name=game_map.chinese_name,
        tracks=[
            track_leaderboard(track, times.get(track.id, []))
            for track in game_map.tracks
        ],
    )


class TrackLookupRequest(BaseModel):
    """Track names to resolve, typically read off a screenshot."""

    names: Annotated[list[Name], Field(min_length=1, max_length=12)]


class MapTrackLeaderboardResponse(TrackLeaderboardResponse):
    map_id: str
    map_name: str
    map_chinese_name: str = ""
    requested_name: str


class TrackLookupResponse(BaseModel):
    tracks: list[MapTrackLeaderboardResponse]
    #: Names that matched no track, so the caller can see what was missed.
    unmatched: list[str]


def map_track_leaderboard(result) -> MapTrackLeaderboardResponse:
    return MapTrackLeaderboardResponse(
        **result.track.model_dump(),
        times=ranked(result.times),
        map_id=result.game_map.id,
        map_name=result.game_map.name,
        map_chinese_name=result.game_map.chinese_name,
        requested_name=result.requested_name,
    )


class MapTrackResponse(Track):
    map_id: str
    map_name: str
    map_chinese_name: str = ""


class TrackListResponse(BaseModel):
    tracks: list[MapTrackResponse]


def map_track(entry) -> MapTrackResponse:
    return MapTrackResponse(
        **entry.track.model_dump(),
        map_id=entry.game_map.id,
        map_name=entry.game_map.name,
        map_chinese_name=entry.game_map.chinese_name,
    )
