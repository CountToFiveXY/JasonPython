"""Firestore persistence and atomic daily ID allocation for the ledger."""

import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter


class ExpenseNotFoundError(LookupError):
    pass


def expense_key(identifier: str) -> tuple[datetime, int]:
    if not re.fullmatch(r"\d{2}-\d{2}-\d{4}:[1-9]\d*", identifier):
        raise ValueError("Expense ID must use MM-DD-YYYY:counter.")
    day, counter = identifier.split(":")
    return datetime.strptime(day, "%m-%d-%Y"), int(counter)


class LedgerRepository:
    def __init__(self, client, *, collection: str | None = None, timezone: str | None = None):
        self.client = client
        name = collection or os.getenv("FIRESTORE_EXPENSE_COLLECTION", "expenses")
        self.expenses = client.collection(name)
        self.counters = client.collection(f"{name}_counters")
        self.timezone = ZoneInfo(timezone or os.getenv("LEDGER_TIMEZONE", "America/Los_Angeles"))

    def list(self) -> list[dict]:
        records = []
        for snapshot in self.expenses.stream():
            # Fail visibly on malformed documents rather than omit money silently.
            expense_key(snapshot.id)
            records.append({**snapshot.to_dict(), "id": snapshot.id})
        return sorted(records, key=lambda record: expense_key(record["id"]))

    def create(self, amount: float, description: str) -> dict:
        day = datetime.now(self.timezone).strftime("%m-%d-%Y")
        return firestore.transactional(self._create)(
            self.client.transaction(), day, amount, description
        )

    def _create(self, transaction, day: str, amount: float, description: str) -> dict:
        counter_ref = self.counters.document(day)
        snapshot = counter_ref.get(transaction=transaction)
        counter = int((snapshot.to_dict() or {}).get("counter", 0))
        # Include existing manually entered documents, even when metadata already exists.
        prefix = f"{day}:"
        query = self.expenses.where(filter=FieldFilter("__name__", ">=", self.expenses.document(prefix)))
        query = query.where(filter=FieldFilter("__name__", "<", self.expenses.document(prefix + "\uf8ff")))
        for record in query.stream(transaction=transaction):
            counter = max(counter, expense_key(record.id)[1])
        identifier = f"{day}:{counter + 1}"
        fields = {"amount": float(amount), "description": description}
        transaction.set(counter_ref, {"counter": counter + 1})
        transaction.create(self.expenses.document(identifier), fields)
        return {"id": identifier, **fields}

    def rename(self, identifier: str, description: str) -> dict:
        expense_key(identifier)
        return firestore.transactional(self._rename)(self.client.transaction(), identifier, description)

    def _rename(self, transaction, identifier: str, description: str) -> dict:
        ref = self.expenses.document(identifier)
        snapshot = ref.get(transaction=transaction)
        if not snapshot.exists:
            raise ExpenseNotFoundError("Expense not found.")
        fields = snapshot.to_dict()
        transaction.update(ref, {"description": description})
        return {**fields, "id": identifier, "description": description}

    def delete(self, identifier: str) -> None:
        expense_key(identifier)
        # Deletion is idempotent; the daily high-water counter is preserved.
        self.expenses.document(identifier).delete()
