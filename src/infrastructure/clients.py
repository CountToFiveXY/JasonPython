import asyncio
import os
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import firebase_admin
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from fastapi import FastAPI, HTTPException, Request, status
from firebase_admin import firestore
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import vision
from google.cloud.firestore_v1 import Client as FirestoreClient
from redis.asyncio import Redis
from temporalio.client import Client

from src.infrastructure.gauntlet_cache_watcher import GauntletCacheWatcher
from src.infrastructure.scheduler import (
    LocalSchedulerController,
    consume_scheduler_controls,
    run_local_scheduler,
)
from src.services.file_transfer import FileTransferService, UploadCodeError, read_upload_code
from src.messaging.config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_SCHEDULER_CONSUMER_GROUP,
    KAFKA_SCHEDULER_TOPIC,
)

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "127.0.0.1:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "jasonapp-xm0830")
# Temporal and Kafka are optional: the core startup runs only Redis and the
# API, so give each a short chance to connect and carry on without it.
OPTIONAL_SERVICE_TIMEOUT = float(os.getenv("OPTIONAL_SERVICE_TIMEOUT", "5"))
START_ALL_HINT = "Click Activate All Services in JasonApp to start it."


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
    await redis_client.ping()
    temporal_client, kafka_producer, scheduler_consumer = await asyncio.gather(
        _connect_temporal(),
        _start_kafka_client(
            "Kafka",
            AIOKafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda value: json.dumps(value).encode("utf-8"),
            ),
        ),
        _start_kafka_client(
            "Kafka scheduler control",
            AIOKafkaConsumer(
                KAFKA_SCHEDULER_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                group_id=KAFKA_SCHEDULER_CONSUMER_GROUP,
                auto_offset_reset="latest",
                value_deserializer=lambda value: json.loads(value.decode("utf-8")),
            ),
        ),
    )
    scheduler_controller = LocalSchedulerController()
    app.state.redis = redis_client
    app.state.temporal = temporal_client
    app.state.kafka_producer = kafka_producer
    app.state.cache_watcher = _start_cache_watcher(app, redis_client)
    app.state.scheduler_controller = scheduler_controller
    app.state.file_transfer = FileTransferService(
        load_upload_code=lambda: _read_upload_code(app),
    )
    app.state.local_scheduler = asyncio.create_task(
        run_local_scheduler(
            is_enabled=scheduler_controller.is_enabled,
        ),
        name="local-scheduler",
    )
    app.state.scheduler_control_consumer = (
        asyncio.create_task(
            consume_scheduler_controls(scheduler_consumer, scheduler_controller),
            name="scheduler-control-consumer",
        )
        if scheduler_consumer is not None
        else None
    )
    try:
        yield
    finally:
        await asyncio.to_thread(app.state.file_transfer.stop)
        tasks = [app.state.local_scheduler]
        if app.state.scheduler_control_consumer is not None:
            tasks.append(app.state.scheduler_control_consumer)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if scheduler_consumer is not None:
            await scheduler_consumer.stop()
        if app.state.cache_watcher is not None:
            app.state.cache_watcher.stop()
        if kafka_producer is not None:
            await kafka_producer.stop()
        await redis_client.aclose()


async def _connect_temporal() -> Client | None:
    """The Temporal client, or None when Temporal is not running."""

    try:
        return await asyncio.wait_for(
            Client.connect(TEMPORAL_ADDRESS, namespace=TEMPORAL_NAMESPACE),
            timeout=OPTIONAL_SERVICE_TIMEOUT,
        )
    except Exception as exc:
        print(
            f"Temporal is not running at {TEMPORAL_ADDRESS} ({exc or type(exc).__name__}); "
            "workflow APIs return 503 until it is started.",
            flush=True,
        )
        return None


async def _start_kafka_client(
    name: str,
    client: AIOKafkaProducer | AIOKafkaConsumer,
) -> AIOKafkaProducer | AIOKafkaConsumer | None:
    """Start a Kafka producer or consumer, or return None when Kafka is down."""

    try:
        await asyncio.wait_for(client.start(), timeout=OPTIONAL_SERVICE_TIMEOUT)
        return client
    except Exception as exc:
        with suppress(Exception):
            await client.stop()
        print(
            f"{name} is not available at {KAFKA_BOOTSTRAP_SERVERS} "
            f"({exc or type(exc).__name__}); messaging APIs return 503 until "
            "Kafka is started.",
            flush=True,
        )
        return None


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
) -> GauntletCacheWatcher | None:
    """Listen to Firestore so outside edits clear the Gauntlet cache.

    Without credentials Gauntlet is unavailable anyway, so the API still
    starts and the cache falls back to expiring on its own.
    """

    try:
        watcher = GauntletCacheWatcher(
            _create_firestore_client(),
            redis_client,
            asyncio.get_running_loop(),
        )
        watcher.start()
    except DefaultCredentialsError:
        print(
            "Firestore credentials are not configured; the Gauntlet cache "
            "will expire on its own instead of following Firestore changes.",
            flush=True,
        )
        return None

    app.state.firestore = watcher._firestore
    print("Watching Firestore for Gauntlet changes.", flush=True)
    return watcher


def _read_upload_code(app: FastAPI) -> str:
    """Read the upload code with the shared Firestore client, made on first use."""

    try:
        if not hasattr(app.state, "firestore"):
            app.state.firestore = _create_firestore_client()
    except DefaultCredentialsError as exc:
        raise UploadCodeError(
            "Firestore credentials are not configured, so the upload code "
            "cannot be read. Set GOOGLE_APPLICATION_CREDENTIALS."
        ) from exc
    return read_upload_code(app.state.firestore)


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


def get_file_transfer(request: Request) -> FileTransferService:
    return request.app.state.file_transfer


def get_temporal(request: Request) -> Client:
    temporal = request.app.state.temporal
    if temporal is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Temporal isn't running. {START_ALL_HINT}",
        )
    return temporal


def get_optional_kafka_producer(request: Request) -> AIOKafkaProducer | None:
    """The producer, or None when Kafka is down; for status checks."""

    return request.app.state.kafka_producer


def get_kafka_producer(request: Request) -> AIOKafkaProducer:
    producer = get_optional_kafka_producer(request)
    if producer is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Kafka isn't running. {START_ALL_HINT}",
        )
    return producer


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
