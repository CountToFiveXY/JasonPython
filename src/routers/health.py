import asyncio

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError
from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.infrastructure.clients import get_kafka_producer, get_redis


router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
async def health_check(
    redis_client: Redis = Depends(get_redis),
    kafka_producer: AIOKafkaProducer = Depends(get_kafka_producer),
) -> dict[str, str]:
    try:
        await redis_client.ping()
    except RedisError as error:
        raise HTTPException(status_code=503, detail="Redis is unavailable") from error

    try:
        metadata_updated = await asyncio.wait_for(
            kafka_producer.client.force_metadata_update(),
            timeout=3,
        )
    except (TimeoutError, KafkaError, OSError):
        metadata_updated = False

    kafka_status = "connected" if metadata_updated else "unavailable"
    application_status = "OK" if metadata_updated else "DEGRADED"
    return {
        "status": application_status,
        "redis": "connected",
        "kafka": kafka_status,
    }
