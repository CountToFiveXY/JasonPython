import asyncio
import os

import firebase_admin
from firebase_admin import firestore
from temporalio import activity


FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "jasonapp-xm0830")
ORDER_COLLECTION = os.getenv("FIRESTORE_ORDER_COLLECTION", "orders")


@activity.defn
async def delete_order(order_id: str) -> str:
    """Delete an expired order document from Firestore."""
    try:
        firebase_app = firebase_admin.get_app()
    except ValueError:
        firebase_app = firebase_admin.initialize_app(
            options={"projectId": FIREBASE_PROJECT_ID}
        )

    client = firestore.client(app=firebase_app)
    document = client.collection(ORDER_COLLECTION).document(order_id)
    await asyncio.to_thread(document.delete)
    return f"Expired order {order_id} deleted"
