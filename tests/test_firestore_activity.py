import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.temporal.activities.firestore import (
    FirestoreDocumentWrite,
    write_firestore_document,
)


class FirestoreActivityTests(unittest.IsolatedAsyncioTestCase):
    async def test_writes_document_and_restores_timestamp_fields(self) -> None:
        document = MagicMock()
        client = MagicMock()
        client.collection.return_value.document.return_value = document
        request = FirestoreDocumentWrite(
            collection="orders",
            document_id="order-123",
            fields={
                "id": "order-123",
                "created": "2026-09-11T12:00:00+00:00",
            },
            timestamp_fields=["created"],
        )

        with (
            patch("src.temporal.activities.firestore.firebase_admin.get_app"),
            patch(
                "src.temporal.activities.firestore.firestore.client",
                return_value=client,
            ),
        ):
            result = await write_firestore_document(request)

        client.collection.assert_called_once_with("orders")
        client.collection.return_value.document.assert_called_once_with("order-123")
        written_fields = document.set.call_args.args[0]
        self.assertEqual(document.set.call_args.kwargs, {"merge": False})
        self.assertEqual(
            written_fields["created"],
            datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(result, "Wrote orders/order-123")

    async def test_merges_partial_document_update(self) -> None:
        document = MagicMock()
        client = MagicMock()
        client.collection.return_value.document.return_value = document
        request = FirestoreDocumentWrite(
            collection="orders",
            document_id="order-123",
            fields={"status": "COMPLETED"},
            timestamp_fields=[],
            merge=True,
        )

        with (
            patch("src.temporal.activities.firestore.firebase_admin.get_app"),
            patch(
                "src.temporal.activities.firestore.firestore.client",
                return_value=client,
            ),
        ):
            await write_firestore_document(request)

        document.set.assert_called_once_with(
            {"status": "COMPLETED"},
            merge=True,
        )


if __name__ == "__main__":
    unittest.main()
