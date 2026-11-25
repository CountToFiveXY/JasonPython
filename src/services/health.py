"""Infrastructure health-check use case."""

from redis.asyncio import Redis
from redis.exceptions import RedisError


class RedisUnavailableError(RuntimeError):
    pass


class HealthService:
    def __init__(self, redis_client: Redis) -> None:
        self._redis_client = redis_client

    async def check(self) -> dict[str, str]:
        try:
            await self._redis_client.ping()
        except RedisError as error:
            raise RedisUnavailableError("Redis is unavailable") from error

        return {"status": "OK", "redis": "connected"}
