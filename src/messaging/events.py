from enum import Enum

from pydantic import BaseModel, Field


class OrderStatus(str, Enum):
    SUCCESS = "SUCCESS"


class OrderStatusEvent(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    status: OrderStatus
