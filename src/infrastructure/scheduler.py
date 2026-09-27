"""Small application-local scheduler used for periodic backend work."""

import asyncio
from collections.abc import Callable
from datetime import datetime


LOCAL_SCHEDULER_INTERVAL_SECONDS = 60.0


def _print_heartbeat(message: str) -> None:
    print(message, flush=True)


async def run_local_scheduler(
    *,
    interval_seconds: float = LOCAL_SCHEDULER_INTERVAL_SECONDS,
    emit: Callable[[str], None] = _print_heartbeat,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Emit a harmless heartbeat immediately and once per interval.

    The optional event makes shutdown and unit tests deterministic. Cancelling
    the task is also safe and is how the FastAPI lifespan normally stops it.
    """

    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be greater than zero")

    stopped = stop_event or asyncio.Event()
    while not stopped.is_set():
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        emit(f"Local scheduler: hello from JasonApp at {timestamp}")
        try:
            await asyncio.wait_for(stopped.wait(), timeout=interval_seconds)
        except TimeoutError:
            pass
