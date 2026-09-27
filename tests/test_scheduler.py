import asyncio
import unittest

from src.infrastructure.scheduler import run_local_scheduler


class LocalSchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def test_emits_immediately_and_stops_cleanly(self) -> None:
        messages: list[str] = []
        stopped = asyncio.Event()
        task = asyncio.create_task(
            run_local_scheduler(
                interval_seconds=60,
                emit=messages.append,
                stop_event=stopped,
            )
        )

        await asyncio.sleep(0)
        stopped.set()
        await task

        self.assertEqual(len(messages), 1)
        self.assertTrue(messages[0].startswith("Local scheduler: hello from JasonApp"))

    async def test_rejects_non_positive_interval(self) -> None:
        with self.assertRaises(ValueError):
            await run_local_scheduler(interval_seconds=0)


if __name__ == "__main__":
    unittest.main()
