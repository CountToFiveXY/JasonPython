"""HTTP schemas for Kafka message publishing."""

from src.messaging.events import OrderStatusEvent


class MessageResponse(OrderStatusEvent):
    topic: str
    partition: int
    offset: int
