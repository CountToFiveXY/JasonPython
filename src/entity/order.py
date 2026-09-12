"""Order entity stored in Firestore."""

from datetime import datetime

from pydantic import BaseModel


class Order(BaseModel):
    """Persistent representation of an order."""

    id: str
    user_id: str
    created: datetime
    expires_at: datetime
