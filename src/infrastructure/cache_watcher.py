"""Change data capture for the leaderboard cache.

The listener is on Firestore itself rather than on this API's write path, so a
document edited in the Firebase console — or by any other client — invalidates
the cache exactly like a write through the API does. Without it the cache can
only be corrected by its TTL, which leaves outside edits invisible for minutes.
"""

import asyncio
from asyncio import AbstractEventLoop
from collections.abc import Iterable

from google.cloud.firestore_v1 import Client as FirestoreClient
from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.services.leaderboard import (
    LAP_TIME_COLLECTION,
    MAP_COLLECTION,
    TRACK_COLLECTION,
    cache_keys_for_path,
)


class LeaderboardCacheWatcher:
    """Clears cached leaderboard reads whenever their documents change."""

    def __init__(
        self,
        firestore_client: FirestoreClient,
        redis_client: Redis,
        loop: AbstractEventLoop,
    ) -> None:
        self._firestore = firestore_client
        self._redis = redis_client
        self._loop = loop
        self._watches: list = []

    def start(self) -> None:
        """Listen to maps, their tracks, and every recorded time."""

        self._watches = [
            self._firestore.collection(MAP_COLLECTION).on_snapshot(self.handle_changes),
            self._firestore.collection_group(TRACK_COLLECTION).on_snapshot(
                self.handle_changes
            ),
            self._firestore.collection_group(LAP_TIME_COLLECTION).on_snapshot(
                self.handle_changes
            ),
        ]

    def stop(self) -> None:
        for watch in self._watches:
            watch.unsubscribe()
        self._watches = []

    def handle_changes(self, snapshots, changes: Iterable, read_time) -> None:
        """Firestore calls this on one of its own threads, not the event loop."""

        keys = {
            key
            for change in changes
            for key in cache_keys_for_path(change.document.reference.path)
        }
        if not keys:
            return
        asyncio.run_coroutine_threadsafe(self._forget(keys), self._loop)

    async def _forget(self, keys: Iterable[str]) -> None:
        try:
            await self._redis.delete(*keys)
        except RedisError:
            # A cache that cannot be cleared still expires on its own.
            pass
