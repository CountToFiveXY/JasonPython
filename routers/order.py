import asyncio
from datetime import datetime, timezone
import os
from uuid import uuid4

from fastapi import APIRouter, Depends, status
from google.cloud.firestore_v1 import Client as FirestoreClient
from pydantic import BaseModel, Field, field_validator
from temporalio.client import Client as TemporalClient

from infrastructure.clients import get_firestore, get_temporal
from temporal.workflows import GreetingWorkflow


router = APIRouter(prefix="/v1/order", tags=["Orders"])
TEMPORAL_TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "utility-api")
ORDER_COLLECTION = os.getenv("FIRESTORE_ORDER_COLLECTION", "orders")


class OrderRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)

    @field_validator("user_id")
    @classmethod
    def normalize_user_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("user_id must not be blank")
        return value


class Order(BaseModel):
    id: str
    user_id: str
    created: datetime


class OrderResponse(Order):
    workflow_id: str


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    request: OrderRequest,
    firestore_client: FirestoreClient = Depends(get_firestore),
    temporal_client: TemporalClient = Depends(get_temporal),
) -> OrderResponse:
    order_id = str(uuid4())
    order = Order(
        id=order_id,
        user_id=request.user_id,
        created=datetime.now(timezone.utc),
    )
    document = firestore_client.collection(ORDER_COLLECTION).document(order_id)

    await asyncio.to_thread(document.create, order.model_dump())
    await temporal_client.start_workflow(
        GreetingWorkflow.run,
        order_id,
        id=order_id,
        task_queue=TEMPORAL_TASK_QUEUE,
    )

    return OrderResponse(**order.model_dump(), workflow_id=order_id)
