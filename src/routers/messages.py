from fastapi import APIRouter, Depends, status

from src.dependencies import get_message_service
from src.messaging.events import MessageEvent, OrderMessageEvent
from src.schemas import MessageResponse, OrderMessageResponse, SchedulingMessageResponse
from src.services import MessageService


router = APIRouter(prefix="/v1/messages", tags=["Kafka"])


@router.post("", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
async def publish_message(
    request: MessageEvent,
    message_service: MessageService = Depends(get_message_service),
) -> MessageResponse:
    published = await message_service.publish(request)
    response_type = (
        OrderMessageResponse
        if isinstance(published.event, OrderMessageEvent)
        else SchedulingMessageResponse
    )
    return response_type(
        **published.event.model_dump(),
        topic=published.topic,
        partition=published.partition,
        offset=published.offset,
    )
