import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from redis.asyncio import Redis


REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
    await redis_client.ping()
    app.state.redis = redis_client
    try:
        yield
    finally:
        await redis_client.aclose()


def get_redis(request: Request) -> Redis:
    return request.app.state.redis
