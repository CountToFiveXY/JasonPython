from fastapi import APIRouter, HTTPException, Request, status
from google.api_core.exceptions import GoogleAPICallError

from src.infrastructure.clients import get_pubsub_publisher
from src.messaging.config import ORDER_SUCCESS_TOPIC
from src.messaging.events import MessageEvent, OrderMessageEvent
from src.schemas import MessageResponse, OrderMessageResponse, SchedulingMessageResponse
from src.services import MessageService


router = APIRouter(prefix="/v1/messages", tags=["Messages"])


@router.post("", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
async def publish_message(event: MessageEvent, request: Request) -> MessageResponse:
    if not isinstance(event, OrderMessageEvent):
        request.app.state.scheduler_controller.apply(event.detailed_payload.action)
        return SchedulingMessageResponse(**event.model_dump())

    service = MessageService(get_pubsub_publisher(request))
    try:
        message_id = await service.publish(event)
    except (GoogleAPICallError, TimeoutError) as exc:
        raise HTTPException(
            status_code=503, detail="Could not confirm the Pub/Sub publish."
        ) from exc
    return OrderMessageResponse(
        **event.model_dump(),
        topic=ORDER_SUCCESS_TOPIC,
        message_id=message_id,
    )
