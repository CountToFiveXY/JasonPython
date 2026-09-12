import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.routers.health import health_check
from src.services import HealthService


class HealthTests(unittest.IsolatedAsyncioTestCase):
    async def test_reports_kafka_connected(self) -> None:
        redis = SimpleNamespace(ping=AsyncMock())
        kafka = SimpleNamespace(
            client=SimpleNamespace(force_metadata_update=AsyncMock(return_value=True))
        )

        response = await health_check(HealthService(redis, kafka))

        self.assertEqual(
            response.model_dump(),
            {"status": "OK", "redis": "connected", "kafka": "connected"},
        )

    async def test_reports_degraded_when_kafka_is_unavailable(self) -> None:
        redis = SimpleNamespace(ping=AsyncMock())
        kafka = SimpleNamespace(
            client=SimpleNamespace(force_metadata_update=AsyncMock(return_value=False))
        )

        response = await health_check(HealthService(redis, kafka))

        self.assertEqual(response.status, "DEGRADED")
        self.assertEqual(response.kafka, "unavailable")


if __name__ == "__main__":
    unittest.main()
