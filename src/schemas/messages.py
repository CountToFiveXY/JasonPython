"""HTTP response schemas for order messages and local scheduling commands."""

from typing import Annotated, TypeAlias

from pydantic import Field

from src.messaging.events import OrderMessageEvent, SchedulingMessageEvent


class OrderMessageResponse(OrderMessageEvent):
    topic: str
    message_id: str


SchedulingMessageResponse = SchedulingMessageEvent

MessageResponse: TypeAlias = Annotated[
    OrderMessageResponse | SchedulingMessageResponse,
    Field(discriminator="event_type"),
]
