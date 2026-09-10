import asyncio
import json
import os

from aiokafka import AIOKafkaConsumer
from pydantic import ValidationError
from temporalio.client import Client

from src.messaging.config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_CONSUMER_GROUP,
    KAFKA_TOPIC,
)
from src.messaging.events import OrderStatus, OrderStatusEvent
from src.temporal.workflows.order import OrderWorkflow


TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "127.0.0.1:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")


async def handle_message(event: dict, temporal_client: Client) -> None:
    """Signal the matching order workflow for a valid success event."""
    try:
        order_event = OrderStatusEvent.model_validate(event)
    except ValidationError as exc:
        print(f"Ignoring invalid Kafka message: {exc}", flush=True)
        return

    if order_event.status is not OrderStatus.SUCCESS:
        return

    workflow_handle = temporal_client.get_workflow_handle(order_event.id)
    await workflow_handle.signal(OrderWorkflow.update_status, order_event.status.value)
    print(
        f"Temporal workflow signaled: id={order_event.id} "
        f"status={order_event.status.value}",
        flush=True,
    )


async def main() -> None:
    temporal_client = await Client.connect(
        TEMPORAL_ADDRESS,
        namespace=TEMPORAL_NAMESPACE,
    )
    consumer = AIOKafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id=KAFKA_CONSUMER_GROUP,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
    )
    await consumer.start()
    print(
        f"Kafka worker polling topic={KAFKA_TOPIC} "
        f"group={KAFKA_CONSUMER_GROUP}",
        flush=True,
    )
    try:
        async for record in consumer:
            while True:
                try:
                    await handle_message(record.value, temporal_client)
                    await consumer.commit()
                    break
                except Exception as exc:
                    print(
                        f"Kafka message handling failed; retrying: {exc}",
                        flush=True,
                    )
                    await asyncio.sleep(5)
    finally:
        await consumer.stop()


if __name__ == "__main__":
    asyncio.run(main())
