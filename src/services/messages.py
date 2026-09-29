"""Kafka message publishing use case."""

from dataclasses import dataclass

from aiokafka import AIOKafkaProducer

from src.messaging.config import KAFKA_ORDER_TOPIC, KAFKA_SCHEDULER_TOPIC
from src.messaging.events import MessageEvent, OrderMessageEvent


@dataclass(frozen=True)
class PublishedMessage:
    event: MessageEvent
    topic: str
    partition: int
    offset: int


class MessageService:
    """Routes typed message envelopes to their dedicated Kafka topics."""

    def __init__(self, producer: AIOKafkaProducer) -> None:
        self._producer = producer

    async def publish(self, event: MessageEvent) -> PublishedMessage:
        payload = event.model_dump(mode="json", by_alias=True)
        if isinstance(event, OrderMessageEvent):
            topic = KAFKA_ORDER_TOPIC
            key = event.detailed_payload.id.encode("utf-8")
        else:
            topic = KAFKA_SCHEDULER_TOPIC
            key = b"scheduler:local"
        metadata = await self._producer.send_and_wait(
            topic,
            payload,
            key=key,
        )
        return PublishedMessage(
            event=event,
            topic=metadata.topic,
            partition=metadata.partition,
            offset=metadata.offset,
        )
