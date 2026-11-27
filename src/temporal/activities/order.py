import asyncio
from dataclasses import dataclass

from temporalio import activity

from src.temporal.activities.firestore import firestore_client


@dataclass
class OrderWorkflowInput:
    order_id: str
    user_id: str
    created: str
    expires_at: str
    collection: str
    status: str = "STARTED"


@activity.defn(name="order.complete")
async def complete(order_id: str, collection: str) -> str:
    """Set the order status to COMPLETED and return the workflow result."""
    document = firestore_client().collection(collection).document(order_id)
    await asyncio.to_thread(document.update, {"status": "COMPLETED"})
    result = f"Order {order_id} completed"
    print(result, flush=True)
    return result
