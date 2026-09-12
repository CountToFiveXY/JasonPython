"""Kafka message publishing use case."""

from dataclasses import dataclass

from aiokafka import AIOKafkaProducer

from src.messaging.config import KAFKA_TOPIC
from src.messaging.events import OrderStatusEvent


@dataclass(frozen=True)
class PublishedMessage:
    event: OrderStatusEvent
    topic: str
    partition: int
    offset: int


class MessageService:
    """Publishes order-status events to Kafka."""

    def __init__(self, producer: AIOKafkaProducer) -> None:
        self._producer = producer

    async def publish(self, event: OrderStatusEvent) -> PublishedMessage:
        payload = event.model_dump(mode="json")
        metadata = await self._producer.send_and_wait(
            KAFKA_TOPIC,
            payload,
            key=payload["id"].encode("utf-8"),
        )
        return PublishedMessage(
            event=event,
            topic=metadata.topic,
            partition=metadata.partition,
            offset=metadata.offset,
        )
