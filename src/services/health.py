"""Infrastructure health-check use case."""

import asyncio

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError
from redis.asyncio import Redis
from redis.exceptions import RedisError


class RedisUnavailableError(RuntimeError):
    pass


class HealthService:
    def __init__(self, redis_client: Redis, kafka_producer: AIOKafkaProducer) -> None:
        self._redis_client = redis_client
        self._kafka_producer = kafka_producer

    async def check(self) -> dict[str, str]:
        try:
            await self._redis_client.ping()
        except RedisError as error:
            raise RedisUnavailableError("Redis is unavailable") from error

        try:
            metadata_updated = await asyncio.wait_for(
                self._kafka_producer.client.force_metadata_update(),
                timeout=3,
            )
        except (TimeoutError, KafkaError, OSError):
            metadata_updated = False

        kafka_status = "connected" if metadata_updated else "unavailable"
        return {
            "status": "OK" if metadata_updated else "DEGRADED",
            "redis": "connected",
            "kafka": kafka_status,
        }
