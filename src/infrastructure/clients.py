import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import firebase_admin
from fastapi import FastAPI, HTTPException, Request, status
from firebase_admin import firestore
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import pubsub_v1, vision
from google.cloud.firestore_v1 import Client as FirestoreClient
from redis.asyncio import Redis
from temporalio.client import Client

from src.infrastructure.gauntlet_cache_watcher import GauntletCacheWatcher
from src.infrastructure.scheduler import (
    LocalSchedulerController,
    run_local_scheduler,
)
from src.services.file_transfer import FileTransferService, UploadCodeError, read_upload_code
from src.temporal.config import (
    TEMPORAL_ADDRESS,
    TEMPORAL_NAMESPACE,
    TEMPORAL_ORDER_NAMESPACE,
)

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "jasonapp-xm0830")
# Core mode starts without Temporal, so give it a short chance to connect.
OPTIONAL_SERVICE_TIMEOUT = float(os.getenv("OPTIONAL_SERVICE_TIMEOUT", "5"))
START_ALL_HINT = "Click Activate All Services in JasonApp to start it."


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
    await redis_client.ping()
    temporal_client, order_temporal_client = await asyncio.gather(
        _connect_temporal(), _connect_temporal(TEMPORAL_ORDER_NAMESPACE)
    )
    scheduler_controller = LocalSchedulerController()
    app.state.redis = redis_client
    app.state.temporal = temporal_client
    app.state.order_temporal = order_temporal_client
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
    try:
        yield
    finally:
        await asyncio.to_thread(app.state.file_transfer.stop)
        app.state.local_scheduler.cancel()
        await asyncio.gather(app.state.local_scheduler, return_exceptions=True)
        if app.state.cache_watcher is not None:
            app.state.cache_watcher.stop()
        if hasattr(app.state, "pubsub_publisher"):
            with suppress(Exception):
                await asyncio.to_thread(app.state.pubsub_publisher.stop)
        await redis_client.aclose()


async def _connect_temporal(namespace: str = TEMPORAL_NAMESPACE) -> Client | None:
    """Connect a namespace client while allowing startup without Temporal."""

    try:
        return await asyncio.wait_for(
            Client.connect(TEMPORAL_ADDRESS, namespace=namespace),
            timeout=OPTIONAL_SERVICE_TIMEOUT,
        )
    except Exception as exc:
        print(
            f"Could not connect to Temporal at {TEMPORAL_ADDRESS} for namespace {namespace} "
            f"({exc or type(exc).__name__}); "
            "workflow APIs return 503 until it is started.",
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
    return _require_temporal(request.app.state.temporal)


def get_order_temporal(request: Request) -> Client:
    return _require_temporal(request.app.state.order_temporal)


def _require_temporal(temporal: Client | None) -> Client:
    if temporal is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Temporal isn't running. {START_ALL_HINT}",
        )
    return temporal


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


def get_pubsub_publisher(request: Request) -> pubsub_v1.PublisherClient:
    """The shared Pub/Sub publisher, created only when its API is used."""

    try:
        if not hasattr(request.app.state, "pubsub_publisher"):
            request.app.state.pubsub_publisher = pubsub_v1.PublisherClient()
        return request.app.state.pubsub_publisher
    except DefaultCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Pub/Sub credentials are not configured. Set "
                "GOOGLE_APPLICATION_CREDENTIALS to the Firebase service-account "
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
