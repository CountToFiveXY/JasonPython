"""HTTP response schemas for Kafka message publishing."""

from typing import Annotated, TypeAlias

from pydantic import Field

from src.messaging.events import OrderMessageEvent, SchedulingMessageEvent


class OrderMessageResponse(OrderMessageEvent):
    topic: str
    partition: int
    offset: int


class SchedulingMessageResponse(SchedulingMessageEvent):
    topic: str
    partition: int
    offset: int


MessageResponse: TypeAlias = Annotated[
    OrderMessageResponse | SchedulingMessageResponse,
    Field(discriminator="event_type"),
]
