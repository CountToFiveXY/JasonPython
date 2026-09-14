"""Application dependency providers."""

from fastapi import Depends
from aiokafka import AIOKafkaProducer
from google.cloud import vision
from google.cloud.firestore_v1 import Client as FirestoreClient
from redis.asyncio import Redis
from temporalio.client import Client as TemporalClient

from src.infrastructure.clients import (
    get_firestore,
    get_vision,
    get_kafka_producer,
    get_redis,
    get_temporal,
)
from src.services import (
    HealthService,
    HelloService,
    ImageService,
    LeaderboardService,
    MessageService,
    OrderService,
    RankingService,
    TextRecognitionService,
    UrlShorteningService,
)


def get_health_service(
    redis_client: Redis = Depends(get_redis),
    kafka_producer: AIOKafkaProducer = Depends(get_kafka_producer),
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


def get_leaderboard_service(
    firestore_client: FirestoreClient = Depends(get_firestore),
    redis_client: Redis = Depends(get_redis),
) -> LeaderboardService:
    """Build a leaderboard service around shared Firestore and Redis clients."""

    return LeaderboardService(firestore_client, redis_client)


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


def get_ranking_service() -> RankingService:
    """Build the stateless ranking image service."""

    return RankingService()


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
