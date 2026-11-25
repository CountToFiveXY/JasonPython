import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.routers.health import health_check
from src.services import HealthService


class HealthTests(unittest.IsolatedAsyncioTestCase):
    async def test_reports_redis_connected(self) -> None:
        redis = SimpleNamespace(ping=AsyncMock())

        response = await health_check(HealthService(redis))

        self.assertEqual(response.model_dump(), {"status": "OK", "redis": "connected"})


if __name__ == "__main__":
    unittest.main()
