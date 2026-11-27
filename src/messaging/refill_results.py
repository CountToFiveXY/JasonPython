import logging

from google.cloud import pubsub_v1
from pydantic import ValidationError

from src.repositories.asphalt_tasks import AsphaltTasks
from src.schemas.asphalt_tasks import RefillResult


SUBSCRIPTION = "projects/jasonapp-xm0830/subscriptions/asphalt_task_results_sub"
logger = logging.getLogger(__name__)


def consume_results(subscriber: pubsub_v1.SubscriberClient, tasks: AsphaltTasks):
    def receive(message):
        try:
            result = RefillResult.model_validate_json(message.data)
        except ValidationError:
            logger.warning("Discarding invalid refill result %s", message.message_id)
            message.ack()
            return
        try:
            tasks.apply(result)
        except Exception:
            logger.exception("Could not save refill result %s", result.task_id)
            message.nack()
            return
        message.ack()

    stream = subscriber.subscribe(SUBSCRIPTION, callback=receive, await_callbacks_on_shutdown=True)

    def log_stop(future):
        if future.exception() is not None:
            logger.error("Refill result subscription stopped: %s", future.exception())

    stream.add_done_callback(log_stop)
    return stream
