import asyncio
from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.temporal.activities.firestore import (
        FirestoreDocumentWrite,
        write_firestore_document,
    )
    from src.temporal.activities.order import complete_order


@dataclass
class OrderWorkflowInput:
    order_id: str
    user_id: str
    created: str
    expires_at: str
    collection: str


@workflow.defn
class OrderWorkflow:
    def __init__(self) -> None:
        self.status: str | None = None

    @workflow.signal
    async def update_status(self, status: str) -> None:
        if status == "SUCCESS":
            self.status = status

    @workflow.run
    async def run(self, request: OrderWorkflowInput) -> str:
        await workflow.execute_activity(
            write_firestore_document,
            FirestoreDocumentWrite(
                collection=request.collection,
                document_id=request.order_id,
                fields={
                    "id": request.order_id,
                    "user_id": request.user_id,
                    "created": request.created,
                    "expires_at": request.expires_at,
                },
                timestamp_fields=["created", "expires_at"],
            ),
            start_to_close_timeout=timedelta(seconds=30),
        )

        try:
            await workflow.wait_condition(
                lambda: self.status == "SUCCESS",
                timeout=timedelta(hours=1),
                timeout_summary="wait-for-order-success",
            )
        except asyncio.TimeoutError:
            return f"Order {request.order_id} timed out waiting for SUCCESS"

        return await workflow.execute_activity(
            complete_order,
            request.order_id,
            start_to_close_timeout=timedelta(seconds=30),
        )
