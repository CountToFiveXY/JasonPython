"""Application dependency providers."""

from fastapi import Depends
from aiokafka import AIOKafkaProducer
from google.cloud import vision
from google.cloud.firestore_v1 import Client as FirestoreClient
from redis.asyncio import Redis
from temporalio.client import Client as TemporalClient

from src.infrastructure.clients import (
    get_file_transfer,
    get_firestore,
    get_vision,
    get_kafka_producer,
    get_optional_kafka_producer,
    get_redis,
    get_temporal,
)
from src.services import (
    FileTransferService,
    HealthService,
    LeaderboardService,
    HelloService,
    ImageService,
    GauntletService,
    MessageService,
    OrderService,
    TextRecognitionService,
    UrlShorteningService,
)


def get_file_transfer_service(
    service: FileTransferService = Depends(get_file_transfer),
) -> FileTransferService:
    """The one LAN file server owned by this API process."""

    return service


def get_health_service(
    redis_client: Redis = Depends(get_redis),
    kafka_producer: AIOKafkaProducer | None = Depends(get_optional_kafka_producer),
) -> HealthService:
    """Build a health service around shared infrastructure clients."""

    return HealthService(redis_client, kafka_producer)


def get_hello_service(
    temporal_client: TemporalClient = Depends(get_temporal),
) -> HelloService:
    """Build a hello service around the shared Temporal client."""

    return HelloService(temporal_client)


def get_image_service() -> ImageService:
    """Build the stateless image service."""

    return ImageService()


def get_gauntlet_service(
    firestore_client: FirestoreClient = Depends(get_firestore),
    redis_client: Redis = Depends(get_redis),
) -> GauntletService:
    """Build a Gauntlet service around shared Firestore and Redis clients."""

    return GauntletService(firestore_client, redis_client)


def get_message_service(
    producer: AIOKafkaProducer = Depends(get_kafka_producer),
) -> MessageService:
    """Build a message service around the shared Kafka producer."""

    return MessageService(producer)


def get_order_service(
    temporal_client: TemporalClient = Depends(get_temporal),
) -> OrderService:
    """Build an order service around the shared Temporal client."""

    return OrderService(temporal_client)


def get_leaderboard_service() -> LeaderboardService:
    """Build the read-only Galaxy Lens leaderboard client."""

    return LeaderboardService()


def get_text_recognition_service(
    vision_client: vision.ImageAnnotatorClient = Depends(get_vision),
) -> TextRecognitionService:
    """Build a text-recognition service around the shared Vision client."""

    return TextRecognitionService(vision_client)


def get_url_shortening_service(
    redis_client: Redis = Depends(get_redis),
) -> UrlShorteningService:
    """Build a URL-shortening service around the shared Redis client."""

    return UrlShorteningService(redis_client)
