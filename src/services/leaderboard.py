"""Leaderboard use cases backed by Cloud Firestore."""

import asyncio
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from google.api_core.exceptions import AlreadyExists
from google.cloud.firestore_v1 import Client as FirestoreClient
from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.entity import GameMap, LapTime, Track


MAP_COLLECTION = os.getenv("FIRESTORE_MAP_COLLECTION", "maps")
TRACK_COLLECTION = "tracks"
LAP_TIME_COLLECTION = "times"
LEADERBOARD_CACHE_TTL_SECONDS = int(os.getenv("LEADERBOARD_CACHE_TTL_SECONDS", "300"))
MAPS_CACHE_KEY = "leaderboard:maps"
CARS_CACHE_KEY = "leaderboard:cars"


def map_cache_key(map_id: str) -> str:
    return f"leaderboard:map:{map_id}"


def cache_keys_for_path(path: str) -> list[str]:
    """The cache keys a changed Firestore document makes stale.

    ``maps/new-york``                          the map list, and that map
    ``maps/new-york/tracks/the-tunnel``        that map
    ``maps/new-york/tracks/the-tunnel/times/c2``  that map, and the car roster

    Anything else belongs to another feature and invalidates nothing.
    """

    parts = path.strip("/").split("/")
    if len(parts) < 2 or parts[0] != MAP_COLLECTION:
        return []

    map_id = parts[1]
    if len(parts) == 2:
        return [MAPS_CACHE_KEY, map_cache_key(map_id)]
    if len(parts) == 4 and parts[2] == TRACK_COLLECTION:
        return [map_cache_key(map_id)]
    if (
        len(parts) == 6
        and parts[2] == TRACK_COLLECTION
        and parts[4] == LAP_TIME_COLLECTION
    ):
        return [map_cache_key(map_id), CARS_CACHE_KEY]
    return []


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
class MapTrack:
    """A track and the map it belongs to, without its times."""

    game_map: GameMap
    track: Track


@dataclass(frozen=True)
class MapTrackTimes:
    """A track together with the map it belongs to, for cross-map listings."""

    game_map: GameMap
    track: Track
    times: list[LapTime]
    #: The name that was looked up, which may be spelled differently.
    requested_name: str


@dataclass(frozen=True)
class TrackLookup:
    tracks: list[MapTrackTimes]
    unmatched: list[str]


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


def _letters_and_digits(value: str) -> str:
    """A name reduced to its letters and digits, for tolerant matching.

    Punctuation is what optical recognition gets wrong most often, so
    ``IT'S A TWISTER!`` and ``ITS A TWISTER`` compare equal.
    """

    return re.sub(r"\W+", "", value.lower(), flags=re.UNICODE)


def _required_identifier(name: str, subject: str) -> str:
    value = identifier(name)
    if not value:
        raise InvalidNameError(f"{subject} name must contain letters or digits")
    return value


class LeaderboardService:
    """Stores maps, their tracks, and the fastest car times on each track."""

    def __init__(
        self,
        firestore_client: FirestoreClient,
        redis_client: Redis | None = None,
    ) -> None:
        self._firestore = firestore_client
        self._redis = redis_client

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

        await self._invalidate_cache(MAPS_CACHE_KEY, self._map_cache_key(game_map.id))
        return game_map

    async def list_maps(self) -> list[GameMap]:
        """Maps in the game's release order, then by name.

        Sorting here rather than in Firestore keeps maps that predate the
        release_order field in the list; an order_by would drop them.
        """

        cached = await self._read_cache(MAPS_CACHE_KEY)
        if isinstance(cached, list):
            return [GameMap.model_validate(value) for value in cached]

        documents = await asyncio.to_thread(lambda: list(self._maps().stream()))
        maps = [GameMap.model_validate(document.to_dict()) for document in documents]
        result = sorted(
            maps,
            key=lambda game_map: (game_map.release_order, game_map.name.lower()),
        )
        await self._write_cache(
            MAPS_CACHE_KEY,
            [game_map.model_dump(mode="json") for game_map in result],
        )
        return result

    async def list_cars(self) -> list[Car]:
        """Every car that holds a time anywhere, for the car selector.

        The same car is often written several ways (``C2`` and ``c2``). Each
        identifier is reported once, under its most-used spelling.
        """

        cached = await self._read_cache(CARS_CACHE_KEY)
        if isinstance(cached, list):
            return [Car(id=value["id"], name=value["name"]) for value in cached]

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
        result = sorted(cars, key=lambda car: car.name.lower())
        await self._write_cache(
            CARS_CACHE_KEY,
            [{"id": car.id, "name": car.name} for car in result],
        )
        return result

    async def list_tracks(self) -> list[MapTrack]:
        """Every track, in map release order then the map's own track order.

        This is what fills a track selector. It is not cached: it is one
        collection-group read on top of the cached map list, and adding a key
        the Firestore watcher does not know about would let it go stale.
        """

        maps = await self.list_maps()
        details = await self._track_details()
        return [
            MapTrack(
                game_map=game_map,
                track=details.get((game_map.id, track.id), track),
            )
            for game_map in maps
            for track in game_map.tracks
        ]

    async def _track_details(self) -> dict[tuple[str, str], Track]:
        """Track documents keyed by map and track, which own the real names."""

        documents = await asyncio.to_thread(
            lambda: list(self._firestore.collection_group(TRACK_COLLECTION).stream())
        )

        details: dict[tuple[str, str], Track] = {}
        for document in documents:
            segments = document.reference.path.split("/")
            if len(segments) < 4:
                continue
            fields = document.to_dict() or {}
            details[(segments[1], segments[3])] = Track(
                id=segments[3],
                name=fields.get("name") or segments[3],
                chinese_name=fields.get("chinese_name", ""),
            )
        return details

    async def lookup_tracks(self, names: list[str]) -> TrackLookup:
        """Resolve track names to their leaderboards, across every map.

        Built for a line-up read off a screenshot: the names arrive as text,
        may belong to different maps, and some may not match anything.
        """

        index: dict[str, tuple[GameMap, Track]] = {}
        for entry in await self.list_tracks():
            for key in {
                entry.track.id,
                _letters_and_digits(entry.track.name),
                _letters_and_digits(entry.track.chinese_name),
            }:
                if key:
                    index.setdefault(key, (entry.game_map, entry.track))

        resolved: list[tuple[str, GameMap, Track]] = []
        unmatched: list[str] = []
        for name in names:
            found = index.get(identifier(name)) or index.get(_letters_and_digits(name))
            if found is None:
                unmatched.append(name)
            else:
                resolved.append((name, found[0], found[1]))

        # One read per distinct map rather than per track, and both tracks of a
        # map come from the same cached payload.
        map_ids = list({game_map.id for _, game_map, _ in resolved})
        results = await asyncio.gather(*(self.map_times(map_id) for map_id in map_ids))
        times_by_map = dict(zip(map_ids, results))

        return TrackLookup(
            tracks=[
                MapTrackTimes(
                    game_map=times_by_map[game_map.id].game_map,
                    track=track,
                    times=times_by_map[game_map.id].times.get(track.id, []),
                    requested_name=name,
                )
                for name, game_map, track in resolved
            ],
            unmatched=unmatched,
        )

    async def map_times(self, map_id: str) -> MapTimes:
        cached = await self._read_cache(self._map_cache_key(map_id))
        if isinstance(cached, dict):
            return MapTimes(
                game_map=GameMap.model_validate(cached["game_map"]),
                times={
                    track_id: [LapTime.model_validate(value) for value in values]
                    for track_id, values in cached["times"].items()
                },
            )

        game_map = await self._read_map(map_id)
        results = await asyncio.gather(
            *(self._ranked_times(map_id, track.id) for track in game_map.tracks)
        )
        result = MapTimes(
            game_map=game_map,
            times={
                track.id: times for track, times in zip(game_map.tracks, results)
            },
        )
        await self._write_cache(
            self._map_cache_key(map_id),
            {
                "game_map": result.game_map.model_dump(mode="json"),
                "times": {
                    track_id: [lap_time.model_dump(mode="json") for lap_time in times]
                    for track_id, times in result.times.items()
                },
            },
        )
        return result

    async def record_lap_time(
        self,
        map_id: str,
        track_id: str,
        car: str,
        seconds: float,
    ) -> TrackTimes:
        track = self._track(await self._read_map(map_id), track_id)
        car_id = _required_identifier(car, "Car")
        lap_time = LapTime(car=car, seconds=round(seconds, 3))

        await asyncio.to_thread(
            self._times(map_id, track_id).document(car_id).set,
            lap_time.model_dump(),
        )
        await self._invalidate_cache(self._map_cache_key(map_id), CARS_CACHE_KEY)
        return TrackTimes(track=track, times=await self._ranked_times(map_id, track_id))

    async def delete_lap_time(self, map_id: str, track_id: str, car: str) -> TrackTimes:
        track = self._track(await self._read_map(map_id), track_id)
        car_id = _required_identifier(car, "Car")
        document = self._times(map_id, track_id).document(car_id)

        snapshot = await asyncio.to_thread(document.get)
        if not snapshot.exists:
            raise LapTimeNotFoundError(f"'{car}' has no time on this track")
        await asyncio.to_thread(document.delete)

        await self._invalidate_cache(self._map_cache_key(map_id), CARS_CACHE_KEY)
        return TrackTimes(track=track, times=await self._ranked_times(map_id, track_id))

    @staticmethod
    def _map_cache_key(map_id: str) -> str:
        return map_cache_key(map_id)

    async def _read_cache(self, key: str):
        if self._redis is None:
            return None
        try:
            value = await self._redis.get(key)
            return json.loads(value) if value is not None else None
        except (RedisError, json.JSONDecodeError, TypeError):
            return None

    async def _write_cache(self, key: str, value) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.set(
                key,
                json.dumps(value, ensure_ascii=False),
                ex=LEADERBOARD_CACHE_TTL_SECONDS,
            )
        except (RedisError, TypeError):
            pass

    async def _invalidate_cache(self, *keys: str) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.delete(*keys)
        except RedisError:
            pass

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

    async def _ranked_times(self, map_id: str, track_id: str) -> list[LapTime]:
        """Every time recorded on a track, fastest first."""

        documents = await asyncio.to_thread(
            lambda: list(
                self._times(map_id, track_id)
                .order_by("seconds")
                .stream()
            )
        )
        return [LapTime.model_validate(document.to_dict()) for document in documents]
