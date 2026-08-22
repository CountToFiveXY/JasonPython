import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from redis.asyncio import Redis
from temporalio.client import Client


REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "127.0.0.1:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
    await redis_client.ping()
    temporal_client = await Client.connect(
        TEMPORAL_ADDRESS,
        namespace=TEMPORAL_NAMESPACE,
    )
    app.state.redis = redis_client
    app.state.temporal = temporal_client
    try:
        yield
    finally:
        await redis_client.aclose()


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


def get_temporal(request: Request) -> Client:
    return request.app.state.temporal
