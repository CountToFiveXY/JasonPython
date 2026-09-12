import unittest

from google.api_core.exceptions import AlreadyExists

from src.routers.leaderboard import (
    create_map,
    delete_lap_time,
    list_maps,
    read_map,
    record_lap_time,
)
from src.schemas import LapTimeRequest, MapCreateRequest
from src.services import LeaderboardService
from src.services.leaderboard import (
    CARS_CACHE_KEY,
    MAP_COLLECTION,
    MAPS_CACHE_KEY,
    InvalidNameError,
    LapTimeNotFoundError,
    MapAlreadyExistsError,
    MapNotFoundError,
    TrackNotFoundError,
    identifier,
)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.values[key] = value

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self.values.pop(key, None)


class FakeSnapshot:
    def __init__(self, fields: dict | None, document_id: str = "") -> None:
        self._fields = fields
        self.id = document_id

    @property
    def exists(self) -> bool:
        return self._fields is not None

    def to_dict(self) -> dict | None:
        return None if self._fields is None else dict(self._fields)


class FakeQuery:
    def __init__(
        self,
        documents: dict[tuple[str, ...], dict],
        path: tuple[str, ...],
        order_field: str | None = None,
        maximum: int | None = None,
    ) -> None:
        self._documents = documents
        self._path = path
        self._order_field = order_field
        self._maximum = maximum

    def order_by(self, field: str) -> "FakeQuery":
        return FakeQuery(self._documents, self._path, field, self._maximum)

    def limit(self, maximum: int) -> "FakeQuery":
        return FakeQuery(self._documents, self._path, self._order_field, maximum)

    def stream(self):
        matches = [
            (path[-1], fields)
            for path, fields in self._documents.items()
            if len(path) == len(self._path) + 1 and path[:-1] == self._path
        ]
        if self._order_field is not None:
            matches.sort(key=lambda match: match[1][self._order_field])
        if self._maximum is not None:
            matches = matches[: self._maximum]
        return iter(
            FakeSnapshot(fields, document_id) for document_id, fields in matches
        )


class FakeCollection(FakeQuery):
    def document(self, document_id: str) -> "FakeDocument":
        return FakeDocument(self._documents, self._path + (document_id,))


class FakeDocument:
    def __init__(self, documents: dict[tuple[str, ...], dict], path: tuple[str, ...]) -> None:
        self._documents = documents
        self.path = path

    def collection(self, name: str) -> FakeCollection:
        return FakeCollection(self._documents, self.path + (name,))

    def get(self) -> FakeSnapshot:
        return FakeSnapshot(self._documents.get(self.path), self.path[-1])

    def set(self, fields: dict) -> None:
        self._documents[self.path] = dict(fields)

    def delete(self) -> None:
        self._documents.pop(self.path, None)


class FakeBatch:
    def __init__(self, documents: dict[tuple[str, ...], dict]) -> None:
        self._documents = documents
        self._writes: list[tuple[str, FakeDocument, dict]] = []

    def create(self, document: FakeDocument, fields: dict) -> None:
        self._writes.append(("create", document, fields))

    def set(self, document: FakeDocument, fields: dict) -> None:
        self._writes.append(("set", document, fields))

    def commit(self) -> None:
        for operation, document, _ in self._writes:
            if operation == "create" and document.path in self._documents:
                raise AlreadyExists("document already exists")
        for _, document, fields in self._writes:
            self._documents[document.path] = dict(fields)


class FakeCollectionGroup:
    """Every document filed under a collection of this name, at any depth."""

    def __init__(self, documents: dict[tuple[str, ...], dict], name: str) -> None:
        self._documents = documents
        self._name = name

    def stream(self):
        return iter(
            FakeSnapshot(fields, path[-1])
            for path, fields in self._documents.items()
            if len(path) >= 2 and path[-2] == self._name
        )


class FakeFirestore:
    def __init__(self) -> None:
        self.documents: dict[tuple[str, ...], dict] = {}

    def collection(self, name: str) -> FakeCollection:
        return FakeCollection(self.documents, (name,))

    def collection_group(self, name: str) -> FakeCollectionGroup:
        return FakeCollectionGroup(self.documents, name)

    def batch(self) -> FakeBatch:
        return FakeBatch(self.documents)


class LeaderboardServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.firestore = FakeFirestore()
        self.service = LeaderboardService(self.firestore)

    async def new_york(self):
        return await self.service.create_map(
            "New York",
            ["A park In A run", "Harbor Sprint"],
        )

    async def test_creates_map_with_identifiers_derived_from_names(self) -> None:
        game_map = await self.new_york()

        self.assertEqual(game_map.id, "new-york")
        self.assertEqual([track.id for track in game_map.tracks], ["a-park-in-a-run", "harbor-sprint"])
        self.assertEqual(
            self.firestore.documents[(MAP_COLLECTION, "new-york")]["name"],
            "New York",
        )
        self.assertEqual(
            self.firestore.documents[(MAP_COLLECTION, "new-york", "tracks", "harbor-sprint")],
            {"id": "harbor-sprint", "name": "Harbor Sprint", "chinese_name": ""},
        )

    async def test_rejects_a_second_map_with_the_same_name(self) -> None:
        await self.new_york()

        with self.assertRaises(MapAlreadyExistsError):
            await self.service.create_map("new york", ["Other One", "Other Two"])

    async def test_rejects_names_without_letters_or_digits(self) -> None:
        with self.assertRaises(InvalidNameError):
            await self.service.create_map("!!!", ["One", "Two"])
        with self.assertRaises(InvalidNameError):
            await self.service.create_map("Berlin", ["One", "---"])

    async def test_rejects_two_tracks_that_share_an_identifier(self) -> None:
        with self.assertRaises(InvalidNameError):
            await self.service.create_map("Berlin", ["Night Run", "night-run"])

    async def test_lists_maps_in_release_order(self) -> None:
        await self.service.create_map("Tokyo", ["One", "Two"])
        await self.new_york()
        await self.service.create_map("Rome", ["Three", "Four"])
        # Rome ships first, New York later; Tokyo has no recorded order.
        self.firestore.documents[(MAP_COLLECTION, "rome")]["release_order"] = 1
        self.firestore.documents[(MAP_COLLECTION, "new-york")]["release_order"] = 9

        names = [game_map.name for game_map in await self.service.list_maps()]

        self.assertEqual(names, ["Rome", "New York", "Tokyo"])

    async def test_reuses_cached_maps_cars_and_map_times(self) -> None:
        redis = FakeRedis()
        service = LeaderboardService(self.firestore, redis)
        await service.create_map("New York", ["One", "Two"])
        await service.record_lap_time("new-york", "one", "C2", 19.62)

        first_maps = await service.list_maps()
        first_cars = await service.list_cars()
        first_times = await service.map_times("new-york")
        self.firestore.documents[(MAP_COLLECTION, "new-york")]["name"] = "Changed"
        self.firestore.documents[
            (MAP_COLLECTION, "new-york", "tracks", "one", "times", "c2")
        ]["seconds"] = 99.0

        self.assertEqual((await service.list_maps())[0].name, first_maps[0].name)
        self.assertEqual((await service.list_cars())[0].name, first_cars[0].name)
        cached_times = await service.map_times("new-york")
        self.assertEqual(cached_times.times["one"], first_times.times["one"])
        self.assertIn(MAPS_CACHE_KEY, redis.values)
        self.assertIn(CARS_CACHE_KEY, redis.values)
        self.assertIn("leaderboard:map:new-york", redis.values)

    async def test_lap_writes_invalidate_cached_leaderboard_and_cars(self) -> None:
        redis = FakeRedis()
        service = LeaderboardService(self.firestore, redis)
        await service.create_map("New York", ["One", "Two"])
        await service.list_cars()
        await service.map_times("new-york")

        await service.record_lap_time("new-york", "one", "C2", 19.62)

        self.assertNotIn(CARS_CACHE_KEY, redis.values)
        self.assertNotIn("leaderboard:map:new-york", redis.values)

    async def test_lists_maps_without_a_release_order_last_by_name(self) -> None:
        await self.service.create_map("Tokyo", ["One", "Two"])
        await self.new_york()

        names = [game_map.name for game_map in await self.service.list_maps()]

        self.assertEqual(names, ["New York", "Tokyo"])

    async def test_keeps_maps_that_predate_the_release_order_field(self) -> None:
        await self.new_york()
        await self.service.create_map("Rome", ["Three", "Four"])
        self.firestore.documents[(MAP_COLLECTION, "rome")]["release_order"] = 1
        # An order_by query in Firestore would drop this document entirely.
        self.firestore.documents[(MAP_COLLECTION, "new-york")].pop("release_order", None)

        names = [game_map.name for game_map in await self.service.list_maps()]

        self.assertEqual(names, ["Rome", "New York"])

    async def test_takes_track_details_from_the_track_document(self) -> None:
        await self.new_york()
        self.firestore.documents[
            (MAP_COLLECTION, "new-york", "tracks", "a-park-in-a-run")
        ]["chinese_name"] = "公园"

        result = await self.service.map_times("new-york")

        self.assertEqual(
            [(track.name, track.chinese_name) for track in result.game_map.tracks],
            [("A park In A run", "公园"), ("Harbor Sprint", "")],
        )

    async def test_falls_back_to_the_maps_track_array(self) -> None:
        await self.new_york()
        # Recorded on the map document instead of the track document.
        tracks = self.firestore.documents[(MAP_COLLECTION, "new-york")]["tracks"]
        tracks[1]["chinese_name"] = "海港冲刺"

        result = await self.service.map_times("new-york")

        self.assertEqual(result.game_map.tracks[1].chinese_name, "海港冲刺")

    async def test_track_chinese_name_reaches_a_recorded_time(self) -> None:
        await self.new_york()
        self.firestore.documents[
            (MAP_COLLECTION, "new-york", "tracks", "a-park-in-a-run")
        ]["chinese_name"] = "公园"

        result = await self.service.record_lap_time(
            "new-york", "a-park-in-a-run", "C2", 19.62
        )

        self.assertEqual(result.track.chinese_name, "公园")

    async def test_reports_a_maps_chinese_name(self) -> None:
        await self.new_york()
        self.firestore.documents[(MAP_COLLECTION, "new-york")]["chinese_name"] = "纽约"

        result = await self.service.map_times("new-york")

        self.assertEqual(result.game_map.chinese_name, "纽约")

    async def test_records_a_time_and_returns_the_track_leaderboard(self) -> None:
        await self.new_york()

        result = await self.service.record_lap_time(
            "new-york", "a-park-in-a-run", "C2", 19.62
        )

        self.assertEqual(result.track.name, "A park In A run")
        self.assertEqual([(time.car, time.seconds) for time in result.times], [("C2", 19.62)])

    async def test_recording_again_replaces_the_cars_previous_time(self) -> None:
        await self.new_york()
        await self.service.record_lap_time("new-york", "a-park-in-a-run", "C2", 19.62)

        result = await self.service.record_lap_time(
            "new-york", "a-park-in-a-run", "c2", 21.40
        )

        self.assertEqual([(time.car, time.seconds) for time in result.times], [("c2", 21.4)])

    async def test_returns_only_the_five_fastest_cars(self) -> None:
        await self.new_york()
        for position, seconds in enumerate([25.0, 19.62, 31.5, 22.25, 20.1, 28.0, 19.7]):
            await self.service.record_lap_time(
                "new-york", "a-park-in-a-run", f"C{position}", seconds
            )

        result = await self.service.record_lap_time(
            "new-york", "a-park-in-a-run", "C9", 18.05
        )

        self.assertEqual(
            [time.seconds for time in result.times],
            [18.05, 19.62, 19.7, 20.1, 22.25],
        )

    async def test_keeps_each_tracks_times_separate(self) -> None:
        await self.new_york()
        await self.service.record_lap_time("new-york", "a-park-in-a-run", "C2", 19.62)

        result = await self.service.map_times("new-york")

        self.assertEqual(len(result.times["a-park-in-a-run"]), 1)
        self.assertEqual(result.times["harbor-sprint"], [])

    async def test_deletes_a_cars_time(self) -> None:
        await self.new_york()
        await self.service.record_lap_time("new-york", "a-park-in-a-run", "C2", 19.62)
        await self.service.record_lap_time("new-york", "a-park-in-a-run", "C3", 20.10)

        result = await self.service.delete_lap_time("new-york", "a-park-in-a-run", "C2")

        self.assertEqual([time.car for time in result.times], ["C3"])

    async def test_deleting_an_unrecorded_car_reports_not_found(self) -> None:
        await self.new_york()

        with self.assertRaises(LapTimeNotFoundError):
            await self.service.delete_lap_time("new-york", "a-park-in-a-run", "C2")

    async def test_reports_unknown_maps_and_tracks(self) -> None:
        await self.new_york()

        with self.assertRaises(MapNotFoundError):
            await self.service.map_times("berlin")
        with self.assertRaises(TrackNotFoundError):
            await self.service.record_lap_time("new-york", "harbor-sprin", "C2", 19.62)

    async def test_records_a_trick_alongside_the_time(self) -> None:
        await self.new_york()

        result = await self.service.record_lap_time(
            "new-york", "a-park-in-a-run", "C2", 19.62, "double shockwave"
        )

        self.assertEqual([time.trick for time in result.times], ["double shockwave"])

    async def test_times_recorded_without_a_trick_read_back_blank(self) -> None:
        await self.new_york()
        # A document written before the trick field existed.
        self.firestore.documents[
            (MAP_COLLECTION, "new-york", "tracks", "a-park-in-a-run", "times", "c2")
        ] = {"car": "C2", "seconds": 19.62}

        result = await self.service.map_times("new-york")

        self.assertEqual(result.times["a-park-in-a-run"][0].trick, "")

    async def test_re_recording_replaces_the_trick_too(self) -> None:
        await self.new_york()
        await self.service.record_lap_time(
            "new-york", "a-park-in-a-run", "C2", 19.62, "double shockwave"
        )

        result = await self.service.record_lap_time(
            "new-york", "a-park-in-a-run", "C2", 19.41, ""
        )

        self.assertEqual([(t.seconds, t.trick) for t in result.times], [(19.41, "")])

    async def test_lists_every_car_once_under_its_most_used_spelling(self) -> None:
        await self.new_york()
        await self.service.create_map("Rome", ["Roman Tumble", "Roman Byroads"])
        # "c2" is written three ways; the most frequent spelling wins.
        await self.service.record_lap_time("new-york", "a-park-in-a-run", "c2", 19.6)
        await self.service.record_lap_time("new-york", "harbor-sprint", "c2", 20.1)
        await self.service.record_lap_time("rome", "roman-tumble", "C2", 18.0)
        await self.service.record_lap_time("rome", "roman-byroads", "杰弟", 19.5)
        await self.service.record_lap_time("new-york", "a-park-in-a-run", "杰弟", 21.0)

        cars = await self.service.list_cars()

        self.assertEqual([(car.id, car.name) for car in cars], [("c2", "c2"), ("杰弟", "杰弟")])

    async def test_car_spelling_ties_break_alphabetically(self) -> None:
        await self.new_york()
        await self.service.record_lap_time("new-york", "a-park-in-a-run", "SF90", 19.6)
        await self.service.record_lap_time("new-york", "harbor-sprint", "sf90", 20.1)

        cars = await self.service.list_cars()

        self.assertEqual([car.name for car in cars], ["SF90"])

    async def test_lists_no_cars_before_any_time_is_recorded(self) -> None:
        await self.new_york()

        self.assertEqual(await self.service.list_cars(), [])

    def test_identifier_collapses_punctuation_and_case(self) -> None:
        self.assertEqual(identifier("A park In A run"), "a-park-in-a-run")
        self.assertEqual(identifier("  São  Paulo!  "), "são-paulo")
        self.assertEqual(identifier("---"), "")

    def test_identifier_keeps_characters_of_every_script(self) -> None:
        self.assertEqual(identifier("旧金山"), "旧金山")
        self.assertEqual(identifier("杰弟"), "杰弟")
        self.assertEqual(identifier("桥+河+星"), "桥-河-星")

    def test_identifier_rejects_names_firestore_reserves(self) -> None:
        for reserved in ["..", ".", "__name__"]:
            self.assertEqual(identifier(reserved), "")

    async def test_stores_chinese_maps_tracks_and_cars(self) -> None:
        game_map = await self.service.create_map("旧金山", ["Railroad", "Tunnel"])
        self.assertEqual(game_map.id, "旧金山")

        result = await self.service.record_lap_time("旧金山", "tunnel", "杰弟", 19.920)
        await self.service.record_lap_time("旧金山", "tunnel", "绿", 19.733)

        result = await self.service.map_times("旧金山")
        self.assertEqual(
            [(time.car, time.seconds) for time in result.times["tunnel"]],
            [("绿", 19.733), ("杰弟", 19.92)],
        )


class LeaderboardRouterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.service = LeaderboardService(FakeFirestore())

    async def test_creates_a_map_with_empty_track_leaderboards(self) -> None:
        response = await create_map(
            MapCreateRequest(name="New York", tracks=["A park In A run", "Harbor Sprint"]),
            self.service,
        )

        self.assertEqual(response.id, "new-york")
        self.assertEqual([track.name for track in response.tracks], ["A park In A run", "Harbor Sprint"])
        self.assertEqual([track.times for track in response.tracks], [[], []])

    async def test_ranks_times_from_one_in_order(self) -> None:
        await create_map(
            MapCreateRequest(name="New York", tracks=["A park In A run", "Harbor Sprint"]),
            self.service,
        )
        await record_lap_time(
            "new-york", "a-park-in-a-run", LapTimeRequest(car="C3", seconds=20.1), self.service
        )
        response = await record_lap_time(
            "new-york", "a-park-in-a-run", LapTimeRequest(car="C2", seconds=19.62), self.service
        )

        self.assertEqual([(time.rank, time.car) for time in response.times], [(1, "C2"), (2, "C3")])

    async def test_lists_maps_for_the_selector(self) -> None:
        await create_map(MapCreateRequest(name="Tokyo", tracks=["One", "Two"]), self.service)

        response = await list_maps(self.service)

        self.assertEqual(
            response.maps[0].model_dump(),
            {"id": "tokyo", "name": "Tokyo", "chinese_name": ""},
        )

    async def test_translates_service_errors_into_status_codes(self) -> None:
        from fastapi import HTTPException

        await create_map(MapCreateRequest(name="Tokyo", tracks=["One", "Two"]), self.service)

        with self.assertRaises(HTTPException) as duplicate:
            await create_map(MapCreateRequest(name="Tokyo", tracks=["Three", "Four"]), self.service)
        self.assertEqual(duplicate.exception.status_code, 409)

        with self.assertRaises(HTTPException) as missing:
            await read_map("berlin", self.service)
        self.assertEqual(missing.exception.status_code, 404)

        with self.assertRaises(HTTPException) as unrecorded:
            await delete_lap_time("tokyo", "one", "C2", self.service)
        self.assertEqual(unrecorded.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
