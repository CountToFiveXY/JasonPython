from uuid import UUID

from firebase_admin import firestore
from google.cloud.firestore_v1 import Client

from src.schemas.asphalt_tasks import AsphaltTaskSnapshot, AsphaltTaskType, RefillResult, RefillStatus


class AsphaltTasks:
    def __init__(self, client: Client):
        self.client = client

    def _document(self, task_id: UUID):
        return self.client.collection("asphalt_tasks").document(str(task_id))

    def create(self, task_id: UUID, task_type: AsphaltTaskType, repeat: int | None = None) -> None:
        data = {
            "type": task_type.value,
            "status": RefillStatus.QUEUED.value,
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
