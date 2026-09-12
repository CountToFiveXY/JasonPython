import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from src.entity import Order
from src.routers.order import create_order
from src.schemas import OrderRequest


class OrderRouterTests(unittest.IsolatedAsyncioTestCase):
    async def test_delegates_order_creation_to_service(self) -> None:
        created = datetime.now(timezone.utc)
        order = Order(
            id="12345678-1234-1234-1234-123456789abc",
            user_id="user-123",
            created=created,
            expires_at=created + timedelta(days=1),
        )
        order_service = AsyncMock()
        order_service.create.return_value = order

        result = await create_order(
            OrderRequest(user_id="user-123"),
            order_service,
        )

        order_service.create.assert_awaited_once_with("user-123")
        self.assertEqual(result.user_id, "user-123")
        self.assertIsInstance(result, Order)
        self.assertEqual(result.workflow_id, result.id)


if __name__ == "__main__":
    unittest.main()
