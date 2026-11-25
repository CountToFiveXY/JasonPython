import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from src.infrastructure import clients


def request_with(**state):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(**state)))


class MissingServiceTests(unittest.TestCase):
    def test_temporal_apis_explain_how_to_start_it(self) -> None:
        with self.assertRaises(HTTPException) as error:
            clients.get_temporal(request_with(temporal=None))
        self.assertEqual(error.exception.status_code, 503)
        self.assertIn("Temporal isn't running", error.exception.detail)
        self.assertIn("Activate All Services", error.exception.detail)

    def test_running_temporal_is_returned(self) -> None:
        temporal = object()
        self.assertIs(clients.get_temporal(request_with(temporal=temporal)), temporal)


class OptionalStartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_temporal_down_starts_without_it(self) -> None:
        with patch.object(clients.Client, "connect", AsyncMock(side_effect=RuntimeError("refused"))):
            self.assertIsNone(await clients._connect_temporal())



if __name__ == "__main__":
    unittest.main()
