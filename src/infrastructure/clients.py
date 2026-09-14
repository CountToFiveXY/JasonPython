import asyncio
import os
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import firebase_admin
from aiokafka import AIOKafkaProducer
from fastapi import FastAPI, HTTPException, Request, status
from firebase_admin import firestore
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import vision
from google.cloud.firestore_v1 import Client as FirestoreClient
from redis.asyncio import Redis
from temporalio.client import Client

from src.infrastructure.cache_watcher import LeaderboardCacheWatcher
from src.messaging.config import KAFKA_BOOTSTRAP_SERVERS

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "127.0.0.1:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "jasonapp-xm0830")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
    await redis_client.ping()
    temporal_client = await Client.connect(
        TEMPORAL_ADDRESS,
        namespace=TEMPORAL_NAMESPACE,
    )
    kafka_producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
    )
    await kafka_producer.start()
    app.state.redis = redis_client
    app.state.temporal = temporal_client
    app.state.kafka_producer = kafka_producer
    app.state.cache_watcher = _start_cache_watcher(app, redis_client)
    try:
        yield
    finally:
        if app.state.cache_watcher is not None:
            app.state.cache_watcher.stop()
        await kafka_producer.stop()
        await redis_client.aclose()


def _create_firestore_client() -> FirestoreClient:
    try:
        firebase_app = firebase_admin.get_app()
    except ValueError:
        firebase_app = firebase_admin.initialize_app(
            options={"projectId": FIREBASE_PROJECT_ID}
        )
    return firestore.client(app=firebase_app)


def _start_cache_watcher(
    app: FastAPI,
    redis_client: Redis,
) -> LeaderboardCacheWatcher | None:
    """Listen to Firestore so outside edits clear the leaderboard cache.

    Without credentials the leaderboard is unavailable anyway, so the API still
    starts and the cache falls back to expiring on its own.
    """

    try:
        watcher = LeaderboardCacheWatcher(
            _create_firestore_client(),
            redis_client,
            asyncio.get_running_loop(),
        )
        watcher.start()
    except DefaultCredentialsError:
        print(
            "Firestore credentials are not configured; the leaderboard cache "
            "will expire on its own instead of following Firestore changes.",
            flush=True,
        )
        return None

    app.state.firestore = watcher._firestore
    print("Watching Firestore for leaderboard changes.", flush=True)
    return watcher


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


def get_temporal(request: Request) -> Client:
    return request.app.state.temporal


def get_kafka_producer(request: Request) -> AIOKafkaProducer:
    return request.app.state.kafka_producer


def get_firestore(request: Request) -> FirestoreClient:
    try:
        if not hasattr(request.app.state, "firestore"):
            request.app.state.firestore = _create_firestore_client()
        return request.app.state.firestore
    except DefaultCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Firestore credentials are not configured. Set "
                "GOOGLE_APPLICATION_CREDENTIALS to a Firebase service-account "
                "JSON file."
            ),
        ) from exc


def get_vision(request: Request) -> vision.ImageAnnotatorClient:
    """The shared Cloud Vision client, built on first use like Firestore."""

    try:
        if not hasattr(request.app.state, "vision"):
            request.app.state.vision = vision.ImageAnnotatorClient()
        return request.app.state.vision
    except DefaultCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Cloud Vision credentials are not configured. Set "
                "GOOGLE_APPLICATION_CREDENTIALS to a service-account JSON file."
            ),
        ) from exc
