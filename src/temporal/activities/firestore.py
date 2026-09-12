import asyncio
from dataclasses import dataclass
from datetime import datetime
import os
from typing import Any

import firebase_admin
from firebase_admin import firestore
from temporalio import activity


FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "jasonapp-xm0830")


@dataclass
class FirestoreDocumentWrite:
    collection: str
    document_id: str
    fields: dict[str, Any]
    timestamp_fields: list[str]


@activity.defn
async def write_firestore_document(request: FirestoreDocumentWrite) -> str:
    """Idempotently write a document so Temporal can safely retry the activity."""
    try:
        firebase_app = firebase_admin.get_app()
    except ValueError:
        firebase_app = firebase_admin.initialize_app(
            options={"projectId": FIREBASE_PROJECT_ID}
        )

    fields = dict(request.fields)
    for field_name in request.timestamp_fields:
        value = fields.get(field_name)
        if isinstance(value, str):
            fields[field_name] = datetime.fromisoformat(value)

    client = firestore.client(app=firebase_app)
    document = client.collection(request.collection).document(request.document_id)
    await asyncio.to_thread(document.set, fields)
    return f"Wrote {request.collection}/{request.document_id}"
