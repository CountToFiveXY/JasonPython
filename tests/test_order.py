import unittest
from unittest.mock import AsyncMock, patch

from routers.order import ORDER_COLLECTION, OrderRequest, create_order


class FakeDocument:
    def __init__(self) -> None:
        self.created_data = None

    def create(self, data) -> None:
        self.created_data = data


class FakeCollection:
    def __init__(self) -> None:
        self.document_id = None
        self.document_ref = FakeDocument()

    def document(self, document_id: str) -> FakeDocument:
        self.document_id = document_id
        return self.document_ref


class FakeFirestore:
    def __init__(self) -> None:
        self.collection_name = None
        self.collection_ref = FakeCollection()

    def collection(self, name: str) -> FakeCollection:
        self.collection_name = name
        return self.collection_ref


class OrderTests(unittest.IsolatedAsyncioTestCase):
    async def test_creates_order_and_starts_workflow_with_same_id(self) -> None:
        firestore = FakeFirestore()
        temporal = AsyncMock()

        with patch(
            "routers.order.uuid4",
            return_value="12345678-1234-1234-1234-123456789abc",
        ):
            result = await create_order(OrderRequest(user_id="user-123"), firestore, temporal)

        self.assertEqual(firestore.collection_name, ORDER_COLLECTION)
        self.assertEqual(firestore.collection_ref.document_id, result.id)
        stored_order = firestore.collection_ref.document_ref.created_data
        self.assertEqual(set(stored_order), {"id", "user_id", "created"})
        self.assertEqual(stored_order["id"], result.id)
        self.assertEqual(stored_order["user_id"], "user-123")
        self.assertEqual(result.user_id, "user-123")
        self.assertIsNotNone(stored_order["created"].tzinfo)
        self.assertEqual(result.workflow_id, result.id)
        temporal.start_workflow.assert_awaited_once()
        _, workflow_order_id = temporal.start_workflow.await_args.args
        self.assertEqual(workflow_order_id, result.id)
        self.assertEqual(temporal.start_workflow.await_args.kwargs["id"], result.id)


if __name__ == "__main__":
    unittest.main()
