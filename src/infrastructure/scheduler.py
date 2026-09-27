"""Small application-local scheduler used for periodic backend work."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime

from aiokafka import AIOKafkaConsumer
from pydantic import ValidationError

from src.messaging.events import SchedulerAction, SchedulingMessageEvent


LOCAL_SCHEDULER_INTERVAL_SECONDS = 60.0
LOCAL_SCHEDULER_CONTROL_POLL_SECONDS = 1.0


def _print_heartbeat(message: str) -> None:
    print(message, flush=True)


class LocalSchedulerController:
    """In-process state changed by the scheduler Kafka consumer."""

    def __init__(self, *, enabled: bool = False) -> None:
        self.enabled = enabled

    async def is_enabled(self) -> bool:
        return self.enabled

    def apply(self, action: SchedulerAction) -> None:
        self.enabled = action is SchedulerAction.START


async def handle_scheduler_control_message(
    event: dict,
    controller: LocalSchedulerController,
) -> bool:
    """Validate and apply one Kafka scheduler command."""

    try:
        message = SchedulingMessageEvent.model_validate(event)
    except ValidationError as exc:
        print(f"Ignoring invalid Kafka scheduler command: {exc}", flush=True)
        return False

    controller.apply(message.detailed_payload.action)
    print(
        f"Local scheduler command applied: {message.detailed_payload.action.value}",
        flush=True,
    )
    return True


async def consume_scheduler_controls(
    consumer: AIOKafkaConsumer,
    controller: LocalSchedulerController,
) -> None:
    """Apply commands arriving on the dedicated scheduler topic."""

    async for record in consumer:
        await handle_scheduler_control_message(record.value, controller)


async def run_local_scheduler(
    *,
    interval_seconds: float = LOCAL_SCHEDULER_INTERVAL_SECONDS,
    poll_seconds: float = LOCAL_SCHEDULER_CONTROL_POLL_SECONDS,
    emit: Callable[[str], None] = _print_heartbeat,
    is_enabled: Callable[[], Awaitable[bool]] | None = None,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Emit a harmless heartbeat immediately and once per interval.

    The optional event makes shutdown and unit tests deterministic. Cancelling
    the task is also safe and is how the FastAPI lifespan normally stops it.
    """

    if interval_seconds <= 0 or poll_seconds <= 0:
        raise ValueError("interval_seconds and poll_seconds must be greater than zero")

    stopped = stop_event or asyncio.Event()
    loop = asyncio.get_running_loop()
    next_heartbeat = 0.0
    was_enabled = False
    while not stopped.is_set():
        enabled = await is_enabled() if is_enabled is not None else True
        now = loop.time()
        if enabled and (not was_enabled or now >= next_heartbeat):
            timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
            emit(f"Local scheduler: hello from JasonApp at {timestamp}")
            next_heartbeat = now + interval_seconds
        was_enabled = enabled
        try:
            await asyncio.wait_for(stopped.wait(), timeout=poll_seconds)
        except TimeoutError:
            pass
