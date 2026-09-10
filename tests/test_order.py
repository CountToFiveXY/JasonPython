import unittest
from unittest.mock import AsyncMock, patch

from src.routers.order import (
    ORDER_CLEANUP_WORKFLOW_SUFFIX,
    ORDER_COLLECTION,
    OrderRequest,
    create_order,
)
from src.temporal.workflows.order import OrderWorkflow
from src.temporal.workflows.order_cleanup import OrderCleanupWorkflow


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
            "src.routers.order.uuid4",
            return_value="12345678-1234-1234-1234-123456789abc",
        ):
            result = await create_order(OrderRequest(user_id="user-123"), firestore, temporal)

        self.assertEqual(firestore.collection_name, ORDER_COLLECTION)
        self.assertEqual(firestore.collection_ref.document_id, result.id)
        stored_order = firestore.collection_ref.document_ref.created_data
        self.assertEqual(set(stored_order), {"id", "user_id", "created", "expires_at"})
        self.assertEqual(stored_order["id"], result.id)
        self.assertEqual(stored_order["user_id"], "user-123")
        self.assertEqual(result.user_id, "user-123")
        self.assertIsNotNone(stored_order["created"].tzinfo)
        self.assertEqual(
            (stored_order["expires_at"] - stored_order["created"]).total_seconds(),
            86_400,
        )
        self.assertEqual(result.expires_at, stored_order["expires_at"])
        self.assertEqual(result.workflow_id, result.id)
        self.assertEqual(temporal.start_workflow.await_count, 2)
        order_call, cleanup_call = temporal.start_workflow.await_args_list
        workflow_run, workflow_order_id = order_call.args
        self.assertEqual(workflow_run, OrderWorkflow.run)
        self.assertEqual(workflow_order_id, result.id)
        self.assertEqual(order_call.kwargs["id"], result.id)
        cleanup_run, cleanup_order_id = cleanup_call.args
        self.assertEqual(cleanup_run, OrderCleanupWorkflow.run)
        self.assertEqual(cleanup_order_id, result.id)
        self.assertEqual(
            cleanup_call.kwargs["id"],
            f"{result.id}{ORDER_CLEANUP_WORKFLOW_SUFFIX}",
        )


if __name__ == "__main__":
    unittest.main()
