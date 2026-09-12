"""Leaderboard use cases backed by Cloud Firestore."""

import asyncio
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from google.api_core.exceptions import AlreadyExists
from google.cloud.firestore_v1 import Client as FirestoreClient

from src.entity import GameMap, LapTime, Track


MAP_COLLECTION = os.getenv("FIRESTORE_MAP_COLLECTION", "maps")
TRACK_COLLECTION = "tracks"
LAP_TIME_COLLECTION = "times"
TOP_LAP_TIMES = 5


class InvalidNameError(ValueError):
    pass


class MapAlreadyExistsError(ValueError):
    pass


class MapNotFoundError(LookupError):
    pass


class TrackNotFoundError(LookupError):
    pass


class LapTimeNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class Car:
    id: str
    name: str


@dataclass(frozen=True)
class TrackTimes:
    track: Track
    times: list[LapTime]


@dataclass(frozen=True)
class MapTimes:
    game_map: GameMap
    times: dict[str, list[LapTime]]


#: Document IDs Firestore reserves for its own use.
_RESERVED_IDENTIFIERS = re.compile(r"^(?:\.|\.\.|__.*__)$")


def identifier(name: str) -> str:
    """Derive a stable document ID from a display name.

    Letters of every script are kept, so Chinese names such as ``旧金山`` keep
    their own characters instead of collapsing to an empty identifier.
    """

    value = re.sub(r"\W+", "-", name.lower(), flags=re.UNICODE).strip("-")
    return "" if _RESERVED_IDENTIFIERS.match(value) else value


def _required_identifier(name: str, subject: str) -> str:
    value = identifier(name)
    if not value:
        raise InvalidNameError(f"{subject} name must contain letters or digits")
    return value


class LeaderboardService:
    """Stores maps, their tracks, and the fastest car times on each track."""

    def __init__(self, firestore_client: FirestoreClient) -> None:
        self._firestore = firestore_client

    async def create_map(self, name: str, track_names: list[str]) -> GameMap:
        tracks: list[Track] = []
        for track_name in track_names:
            track_id = _required_identifier(track_name, "Track")
            if any(track.id == track_id for track in tracks):
                raise InvalidNameError("A map's tracks must have different names")
            tracks.append(Track(id=track_id, name=track_name))

        game_map = GameMap(
            id=_required_identifier(name, "Map"),
            name=name,
            tracks=tracks,
        )

        map_document = self._maps().document(game_map.id)
        batch = self._firestore.batch()
        batch.create(map_document, game_map.model_dump())
        for track in game_map.tracks:
            batch.set(
                map_document.collection(TRACK_COLLECTION).document(track.id),
                track.model_dump(),
            )

        try:
            await asyncio.to_thread(batch.commit)
        except AlreadyExists as exc:
            raise MapAlreadyExistsError(f"Map '{name}' already exists") from exc

        return game_map

    async def list_maps(self) -> list[GameMap]:
        """Maps in the game's release order, then by name.

        Sorting here rather than in Firestore keeps maps that predate the
        release_order field in the list; an order_by would drop them.
        """

        documents = await asyncio.to_thread(lambda: list(self._maps().stream()))
        maps = [GameMap.model_validate(document.to_dict()) for document in documents]
        return sorted(maps, key=lambda game_map: (game_map.release_order, game_map.name.lower()))

    async def list_cars(self) -> list[Car]:
        """Every car that holds a time anywhere, for the car selector.

        The same car is often written several ways (``C2`` and ``c2``). Each
        identifier is reported once, under its most-used spelling.
        """

        documents = await asyncio.to_thread(
            lambda: list(self._firestore.collection_group(LAP_TIME_COLLECTION).stream())
        )

        spellings: dict[str, Counter] = defaultdict(Counter)
        for document in documents:
            name = (document.to_dict() or {}).get("car")
            if isinstance(name, str) and name:
                spellings[identifier(name)][name] += 1

        cars = [
            # Sorting first makes the tie-break alphabetical rather than arbitrary.
            Car(id=car_id, name=max(sorted(counter), key=counter.__getitem__))
            for car_id, counter in spellings.items()
            if car_id
        ]
        return sorted(cars, key=lambda car: car.name.lower())

    async def map_times(self, map_id: str) -> MapTimes:
        game_map = await self._read_map(map_id)
        results = await asyncio.gather(
            *(self._top_times(map_id, track.id) for track in game_map.tracks)
        )
        return MapTimes(
            game_map=game_map,
            times={
                track.id: times for track, times in zip(game_map.tracks, results)
            },
        )

    async def record_lap_time(
        self,
        map_id: str,
        track_id: str,
        car: str,
        seconds: float,
        trick: str = "",
    ) -> TrackTimes:
        track = self._track(await self._read_map(map_id), track_id)
        car_id = _required_identifier(car, "Car")
        lap_time = LapTime(car=car, seconds=round(seconds, 3), trick=trick)

        await asyncio.to_thread(
            self._times(map_id, track_id).document(car_id).set,
            lap_time.model_dump(),
        )
        return TrackTimes(track=track, times=await self._top_times(map_id, track_id))

    async def delete_lap_time(self, map_id: str, track_id: str, car: str) -> TrackTimes:
        track = self._track(await self._read_map(map_id), track_id)
        car_id = _required_identifier(car, "Car")
        document = self._times(map_id, track_id).document(car_id)

        snapshot = await asyncio.to_thread(document.get)
        if not snapshot.exists:
            raise LapTimeNotFoundError(f"'{car}' has no time on this track")
        await asyncio.to_thread(document.delete)

        return TrackTimes(track=track, times=await self._top_times(map_id, track_id))

    def _maps(self):
        return self._firestore.collection(MAP_COLLECTION)

    def _times(self, map_id: str, track_id: str):
        return (
            self._maps()
            .document(map_id)
            .collection(TRACK_COLLECTION)
            .document(track_id)
            .collection(LAP_TIME_COLLECTION)
        )

    async def _read_map(self, map_id: str) -> GameMap:
        snapshot = await asyncio.to_thread(self._maps().document(map_id).get)
        if not snapshot.exists:
            raise MapNotFoundError(f"Map '{map_id}' not found")

        game_map = GameMap.model_validate(snapshot.to_dict())
        tracks = await self._describe_tracks(map_id, game_map.tracks)
        return game_map.model_copy(update={"tracks": tracks})

    async def _describe_tracks(self, map_id: str, tracks: list[Track]) -> list[Track]:
        """Take each track's display details from its own document.

        The map document's array fixes which tracks a map has and the order
        they are shown in; the track documents own the name and Chinese name,
        so there is one obvious place to edit them. A detail missing from the
        document falls back to the array.
        """

        documents = await asyncio.to_thread(
            lambda: list(
                self._maps().document(map_id).collection(TRACK_COLLECTION).stream()
            )
        )
        details = {document.id: (document.to_dict() or {}) for document in documents}

        return [
            Track(
                id=track.id,
                name=details.get(track.id, {}).get("name") or track.name,
                chinese_name=(
                    details.get(track.id, {}).get("chinese_name") or track.chinese_name
                ),
            )
            for track in tracks
        ]

    @staticmethod
    def _track(game_map: GameMap, track_id: str) -> Track:
        for track in game_map.tracks:
            if track.id == track_id:
                return track
        raise TrackNotFoundError(
            f"Map '{game_map.id}' has no track '{track_id}'"
        )

    async def _top_times(self, map_id: str, track_id: str) -> list[LapTime]:
        documents = await asyncio.to_thread(
            lambda: list(
                self._times(map_id, track_id)
                .order_by("seconds")
                .limit(TOP_LAP_TIMES)
                .stream()
            )
        )
        return [LapTime.model_validate(document.to_dict()) for document in documents]
