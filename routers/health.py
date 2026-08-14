from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis
from redis.exceptions import RedisError

from database import get_redis


router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
async def health_check(
    redis_client: Redis = Depends(get_redis),
) -> dict[str, str]:
    try:
        await redis_client.ping()
    except RedisError as error:
        raise HTTPException(status_code=503, detail="Redis is unavailable") from error
    return {"status": "OK", "redis": "connected"}
