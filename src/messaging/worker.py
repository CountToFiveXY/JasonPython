"""Consume order successes and signal the corresponding Temporal workflow."""

import asyncio
import logging
import signal
from datetime import timedelta

from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.subscriber.message import Message
from pydantic import ValidationError
from temporalio.client import Client, RPCError, RPCStatusCode

from src.infrastructure.clients import TEMPORAL_ADDRESS, TEMPORAL_NAMESPACE
from src.messaging.config import ORDER_SUCCESS_SUBSCRIPTION
from src.messaging.events import OrderMessageEvent
from src.temporal.workflows.order import OrderWorkflow


logger = logging.getLogger(__name__)


async def handle_message(message: Message, temporal_client: Client) -> None:
    try:
        event = OrderMessageEvent.model_validate_json(message.data).detailed_payload
    except ValidationError:
        logger.warning("Discarding invalid order success message %s", message.message_id)
        message.ack()
        return

    try:
        await temporal_client.get_workflow_handle(event.id).signal(
            OrderWorkflow.update_status,
            event.status.value,
            rpc_timeout=timedelta(seconds=10),
        )
    except RPCError as exc:
        if exc.status == RPCStatusCode.NOT_FOUND:
            logger.warning("Order workflow %s is unavailable for signaling: %s", event.id, exc)
            message.ack()
            return
        logger.exception("Could not signal order workflow %s", event.id)
        message.nack()
        return
    except Exception:
        logger.exception("Could not signal order workflow %s", event.id)
        message.nack()
        return

    message.ack()


async def main() -> None:
    temporal_client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEMPORAL_NAMESPACE)
    loop = asyncio.get_running_loop()

    def callback(message: Message) -> None:
        asyncio.run_coroutine_threadsafe(handle_message(message, temporal_client), loop).result()

    with pubsub_v1.SubscriberClient() as subscriber:
        stream = subscriber.subscribe(
            ORDER_SUCCESS_SUBSCRIPTION,
            callback=callback,
            flow_control=pubsub_v1.types.FlowControl(max_messages=10),
            await_callbacks_on_shutdown=True,
        )
        loop.add_signal_handler(signal.SIGTERM, stream.cancel)
        loop.add_signal_handler(signal.SIGINT, stream.cancel)
        logger.info("Listening on %s", ORDER_SUCCESS_SUBSCRIPTION)
        finished = asyncio.wrap_future(stream)
        try:
            await asyncio.shield(finished)
        finally:
            loop.remove_signal_handler(signal.SIGTERM)
            loop.remove_signal_handler(signal.SIGINT)
            stream.cancel()
            await finished


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
