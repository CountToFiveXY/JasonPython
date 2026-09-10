from aiokafka import AIOKafkaProducer
from fastapi import APIRouter, Depends, status

from src.infrastructure.clients import get_kafka_producer
from src.messaging.config import KAFKA_TOPIC
from src.messaging.events import OrderStatusEvent


router = APIRouter(prefix="/v1/messages", tags=["Kafka"])


class MessageResponse(OrderStatusEvent):
    topic: str
    partition: int
    offset: int


@router.post("", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
async def publish_message(
    request: OrderStatusEvent,
    producer: AIOKafkaProducer = Depends(get_kafka_producer),
) -> MessageResponse:
    event = request.model_dump(mode="json")
    metadata = await producer.send_and_wait(
        KAFKA_TOPIC,
        event,
        key=event["id"].encode("utf-8"),
    )
    return MessageResponse(
        **event,
        topic=metadata.topic,
        partition=metadata.partition,
        offset=metadata.offset,
    )
