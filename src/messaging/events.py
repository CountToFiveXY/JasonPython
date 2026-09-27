from enum import Enum
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field


class OrderStatus(str, Enum):
    SUCCESS = "SUCCESS"


class OrderStatusEvent(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    status: OrderStatus


class SchedulerAction(str, Enum):
    START = "START"
    STOP = "STOP"


class SchedulerControlEvent(BaseModel):
    action: SchedulerAction


class MessageEventType(str, Enum):
    ORDER = "ORDER"
    SCHEDULING = "SCHEDULING"


class OrderMessageEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_type: Literal[MessageEventType.ORDER] = Field(alias="EventType")
    detailed_payload: OrderStatusEvent


class SchedulingMessageEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_type: Literal[MessageEventType.SCHEDULING] = Field(alias="EventType")
    detailed_payload: SchedulerControlEvent


MessageEvent: TypeAlias = Annotated[
    OrderMessageEvent | SchedulingMessageEvent,
    Field(discriminator="event_type"),
]
