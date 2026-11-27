from dataclasses import dataclass

from temporalio import activity

from src.temporal.activities.firestore import FirestoreDocumentWrite, write_firestore_document


@dataclass
class OrderWorkflowInput:
    order_id: str
    user_id: str
    created: str
    expires_at: str
    collection: str
    status: str = "STARTED"


@activity.defn(name="order.create")
async def create(request: OrderWorkflowInput) -> None:
    """Write the initial order document."""
    await write_firestore_document(
        FirestoreDocumentWrite(
            collection=request.collection,
            document_id=request.order_id,
            fields={
                "id": request.order_id,
                "user_id": request.user_id,
                "created": request.created,
                "expires_at": request.expires_at,
                "status": "STARTED",
            },
            timestamp_fields=["created", "expires_at"],
        )
    )


@activity.defn(name="order.record_payout")
async def record_payout(
    order_id: str, collection: str, payout_id: str, payout_status: str | None = None
) -> None:
    fields = {"payout_id": payout_id}
    if payout_status is not None:
        fields["payout_status"] = payout_status
    await write_firestore_document(
        FirestoreDocumentWrite(
            collection=collection,
            document_id=order_id,
            fields=fields,
            timestamp_fields=[],
            merge=True,
        )
    )


@activity.defn(name="order.complete")
async def complete(order_id: str, collection: str) -> str:
    """Set the order status to COMPLETED and return the workflow result."""
    await write_firestore_document(
        FirestoreDocumentWrite(
            collection=collection,
            document_id=order_id,
            fields={"status": "COMPLETED"},
            timestamp_fields=[],
            merge=True,
        )
    )
    result = f"Order {order_id} completed"
    print(result, flush=True)
    return result
