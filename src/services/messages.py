"""Publish order success events to Google Cloud Pub/Sub."""

import asyncio

from google.cloud import pubsub_v1

from src.messaging.config import ORDER_SUCCESS_TOPIC
from src.messaging.events import OrderMessageEvent


class MessageService:
    def __init__(self, publisher: pubsub_v1.PublisherClient) -> None:
        self._publisher = publisher

    async def publish(self, event: OrderMessageEvent) -> str:
        data = event.model_dump_json(by_alias=True).encode("utf-8")
        future = self._publisher.publish(ORDER_SUCCESS_TOPIC, data)
        return await asyncio.to_thread(future.result, timeout=10)
