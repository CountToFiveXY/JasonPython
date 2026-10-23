import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiokafka import AIOKafkaProducer
from fastapi import HTTPException

from src.infrastructure import clients
from src.services import HealthService


def request_with(**state):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(**state)))


class MissingServiceTests(unittest.TestCase):
    def test_temporal_apis_explain_how_to_start_it(self) -> None:
        with self.assertRaises(HTTPException) as error:
            clients.get_temporal(request_with(temporal=None))
        self.assertEqual(error.exception.status_code, 503)
        self.assertIn("Temporal isn't running", error.exception.detail)
        self.assertIn("Activate All Services", error.exception.detail)

    def test_kafka_apis_explain_how_to_start_it(self) -> None:
        with self.assertRaises(HTTPException) as error:
            clients.get_kafka_producer(request_with(kafka_producer=None))
        self.assertEqual(error.exception.status_code, 503)
        self.assertIn("Kafka isn't running", error.exception.detail)

    def test_status_checks_still_get_a_missing_producer(self) -> None:
        self.assertIsNone(clients.get_optional_kafka_producer(request_with(kafka_producer=None)))

    def test_running_services_are_returned(self) -> None:
        temporal, producer = object(), object()
        self.assertIs(clients.get_temporal(request_with(temporal=temporal)), temporal)
        self.assertIs(clients.get_kafka_producer(request_with(kafka_producer=producer)), producer)


class OptionalStartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_temporal_down_starts_without_it(self) -> None:
        with patch.object(clients.Client, "connect", AsyncMock(side_effect=RuntimeError("refused"))):
            self.assertIsNone(await clients._connect_temporal())

    async def test_kafka_down_starts_without_it(self) -> None:
        producer = AIOKafkaProducer(bootstrap_servers="127.0.0.1:1")
        with patch.object(clients, "OPTIONAL_SERVICE_TIMEOUT", 2):
            self.assertIsNone(await clients._start_kafka_client("Kafka", producer))

    async def test_health_reports_kafka_unavailable_without_a_producer(self) -> None:
        redis = SimpleNamespace(ping=AsyncMock())
        self.assertEqual(
            await HealthService(redis, None).check(),
            {"status": "DEGRADED", "redis": "connected", "kafka": "unavailable"},
        )


if __name__ == "__main__":
    unittest.main()
