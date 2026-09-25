"""Order entity stored in Firestore."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class OrderStatus(str, Enum):
    """Lifecycle states persisted with an order."""

    STARTED = "STARTED"
    COMPLETED = "COMPLETED"


class Order(BaseModel):
    """Persistent representation of an order."""

    id: str
    user_id: str
    created: datetime
    expires_at: datetime
    status: OrderStatus
