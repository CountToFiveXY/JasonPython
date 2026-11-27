from uuid import UUID

from firebase_admin import firestore
from google.cloud.firestore_v1 import Client

from src.schemas.asphalt_tasks import (
    AsphaltTaskHistoryEntry, AsphaltTaskSnapshot, AsphaltTaskType, RefillResult, RefillStatus,
)


class AsphaltTasks:
    def __init__(self, client: Client):
        self.client = client

    def _document(self, task_id: UUID):
        return self.client.collection("asphalt_tasks").document(str(task_id))

    def create(self, task_id: UUID, task_type: AsphaltTaskType, repeat: int | None = None) -> None:
        data = {
            "type": task_type.value,
            "status": RefillStatus.QUEUED.value,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        if repeat is not None:
            data["repeat"] = repeat
        self._document(task_id).create(data)

    def get(self, task_id: UUID) -> AsphaltTaskSnapshot | None:
        data = self._document(task_id).get().to_dict()
        if data is None:
            return None
        return AsphaltTaskSnapshot(
            task_id=task_id, type=data["type"], status=data["status"], error=data.get("error")
        )

    def apply(self, result: RefillResult) -> None:
        document = self._document(result.task_id)

        @firestore.transactional
        def update(transaction):
            data = document.get(transaction=transaction).to_dict()
            if data is None or data["status"] not in (RefillStatus.QUEUED, RefillStatus.RUNNING):
                return
            if result.status == RefillStatus.QUEUED or data["status"] == result.status:
                return
            transaction.update(document, {
                "status": result.status.value,
                "error": result.error,
                "updated_at": firestore.SERVER_TIMESTAMP,
            })

        update(self.client.transaction())

    def recent(self) -> list[AsphaltTaskHistoryEntry]:
        collection = self.client.collection("asphalt_tasks")
        documents = list(collection.order_by("created_at", direction="DESCENDING").limit(10).stream())
        if len(documents) < 10:
            # Existing refill records predate the created_at field.
            documents.extend(
                doc for doc in collection.order_by("updated_at", direction="DESCENDING").limit(20).stream()
                if "created_at" not in doc.to_dict()
            )
        entries = []
        for doc in documents:
            data = doc.to_dict()
            entries.append(AsphaltTaskHistoryEntry(
                task_id=UUID(doc.id), type=data["type"], status=data["status"],
                error=data.get("error"), repeat=data.get("repeat"),
                requested_at=data.get("created_at") or doc.create_time,
            ))
        return sorted(entries, key=lambda entry: entry.requested_at, reverse=True)[:10]
