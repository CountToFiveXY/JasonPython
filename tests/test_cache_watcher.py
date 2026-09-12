import asyncio
import unittest

from src.infrastructure.cache_watcher import LeaderboardCacheWatcher
from src.services.leaderboard import (
    CARS_CACHE_KEY,
    MAPS_CACHE_KEY,
    cache_keys_for_path,
    map_cache_key,
)
from tests.test_leaderboard import FakeFirestore, FakeRedis


class FakeReference:
    def __init__(self, path: str) -> None:
        self.path = path


class FakeChange:
    """Stands in for a Firestore DocumentChange."""

    def __init__(self, path: str) -> None:
        self.document = type("Snapshot", (), {"reference": FakeReference(path)})()


class CacheKeyTests(unittest.TestCase):
    def test_a_changed_map_clears_the_list_and_that_map(self) -> None:
        self.assertEqual(
            cache_keys_for_path("maps/new-york"),
            [MAPS_CACHE_KEY, map_cache_key("new-york")],
        )

    def test_a_changed_track_clears_its_map(self) -> None:
        self.assertEqual(
            cache_keys_for_path("maps/new-york/tracks/the-tunnel"),
            [map_cache_key("new-york")],
        )

    def test_a_changed_time_clears_its_map_and_the_car_roster(self) -> None:
        self.assertEqual(
            cache_keys_for_path("maps/new-york/tracks/the-tunnel/times/c2"),
            [map_cache_key("new-york"), CARS_CACHE_KEY],
        )

    def test_documents_of_other_features_clear_nothing(self) -> None:
        for path in ["orders/order-123", "maps", "", "short_url:abc"]:
            self.assertEqual(cache_keys_for_path(path), [], path)


class CacheWatcherTests(unittest.IsolatedAsyncioTestCase):
    async def watcher(self, redis: FakeRedis) -> LeaderboardCacheWatcher:
        return LeaderboardCacheWatcher(
            FakeFirestore(), redis, asyncio.get_running_loop()
        )

    async def test_an_edit_made_outside_the_api_clears_the_cache(self) -> None:
        redis = FakeRedis()
        redis.values = {
            MAPS_CACHE_KEY: "[]",
            map_cache_key("auckland"): "{}",
            map_cache_key("rome"): "{}",
        }
        watcher = await self.watcher(redis)

        # What a Chinese name edited in the Firebase console looks like.
        watcher.handle_changes(
            None, [FakeChange("maps/auckland/tracks/straight-sprint")], None
        )
        await asyncio.sleep(0.01)

        self.assertNotIn(map_cache_key("auckland"), redis.values)
        # Untouched maps keep their cached copy.
        self.assertIn(map_cache_key("rome"), redis.values)
        self.assertIn(MAPS_CACHE_KEY, redis.values)

    async def test_changes_elsewhere_in_firestore_are_ignored(self) -> None:
        redis = FakeRedis()
        redis.values = {MAPS_CACHE_KEY: "[]"}
        watcher = await self.watcher(redis)

        watcher.handle_changes(None, [FakeChange("orders/order-123")], None)
        await asyncio.sleep(0.01)

        self.assertIn(MAPS_CACHE_KEY, redis.values)

    async def test_one_batch_of_changes_clears_every_affected_key(self) -> None:
        redis = FakeRedis()
        redis.values = {
            MAPS_CACHE_KEY: "[]",
            CARS_CACHE_KEY: "[]",
            map_cache_key("rome"): "{}",
            map_cache_key("paris"): "{}",
        }
        watcher = await self.watcher(redis)

        watcher.handle_changes(
            None,
            [
                FakeChange("maps/rome/tracks/roman-tumble/times/c2"),
                FakeChange("maps/paris"),
            ],
            None,
        )
        await asyncio.sleep(0.01)

        self.assertEqual(redis.values, {})

    async def test_a_redis_failure_does_not_escape(self) -> None:
        class BrokenRedis(FakeRedis):
            async def delete(self, *keys: str) -> None:
                from redis.exceptions import RedisError

                raise RedisError("down")

        watcher = await self.watcher(BrokenRedis())
        watcher.handle_changes(None, [FakeChange("maps/rome")], None)
        await asyncio.sleep(0.01)


if __name__ == "__main__":
    unittest.main()
