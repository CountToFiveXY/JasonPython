"""Ledger contract tests without touching the user's Firestore database."""

import copy
import unittest
from datetime import datetime
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.dependencies import get_ledger_service
from src.repositories.ledger import LedgerRepository
from src.routers.ledger import router
from src.services.ledger import LedgerService


class Snapshot:
    def __init__(self, ref):
        self.reference = ref
        self.id = ref.id
        self.fields = copy.deepcopy(ref.client.data.get(ref.path))
        self.exists = self.fields is not None

    def to_dict(self):
        return self.fields


class Document:
    def __init__(self, client, collection, identifier):
        self.client = client
        self.id = identifier
        self.path = (collection, identifier)

    def get(self, transaction=None):
        return Snapshot(self)

    def delete(self):
        self.client.data.pop(self.path, None)


class Collection:
    def __init__(self, client, name, filters=()):
        self.client = client
        self.name = name
        self.filters = filters

    def document(self, identifier):
        return Document(self.client, self.name, identifier)

    def where(self, *, filter):
        return Collection(self.client, self.name, (*self.filters, filter))

    def stream(self, transaction=None):
        for collection, identifier in list(self.client.data):
            if collection != self.name:
                continue
            if all(
                identifier >= f.value.id if f.op_string == ">=" else identifier < f.value.id
                for f in self.filters
            ):
                yield self.document(identifier).get(transaction)


class Transaction:
    def __init__(self, client):
        self.client = client
        self.writes = []

    def set(self, ref, fields):
        self.writes.append(("set", ref, fields))

    def create(self, ref, fields):
        self.writes.append(("create", ref, fields))

    def update(self, ref, fields):
        self.writes.append(("update", ref, fields))

    def commit(self):
        staged = copy.deepcopy(self.client.data)
        for action, ref, fields in self.writes:
            if action == "create" and ref.path in staged:
                raise AssertionError("Existing expense must never be overwritten")
            if action == "update":
                staged[ref.path].update(fields)
            else:
                staged[ref.path] = fields
        self.client.data = staged


def fake_transactional(operation):
    def run(transaction, *args):
        result = operation(transaction, *args)
        transaction.commit()
        return result
    return run


class Client:
    def __init__(self):
        self.data = {}

    def collection(self, name):
        return Collection(self, name)

    def transaction(self):
        return Transaction(self)


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.client = Client()
        self.repository = LedgerRepository(self.client, collection="expenses", timezone="America/Los_Angeles")
        self.app = FastAPI()
        self.app.include_router(router)
        self.app.dependency_overrides[get_ledger_service] = lambda: LedgerService(self.repository)
        self.http = TestClient(self.app)
        self.transaction_patch = patch("src.repositories.ledger.firestore.transactional", fake_transactional)
        self.transaction_patch.start()
        self.addCleanup(self.transaction_patch.stop)
        self.clock = patch("src.repositories.ledger.datetime")
        self.mock_clock = self.clock.start()
        self.mock_clock.now.return_value = datetime(2026, 1, 1)
        self.mock_clock.strptime.side_effect = datetime.strptime
        self.addCleanup(self.clock.stop)

    def create(self, amount=12.34, description="  Coffee  "):
        return self.http.post("/v1/ledger/expenses", json={"amount": amount, "description": description})

    def test_crud_contract_and_double_storage(self):
        response = self.create()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"id": "01-01-2026:1", "amount": 12.34, "description": "Coffee"})
        fields = self.client.data[("expenses", "01-01-2026:1")]
        self.assertEqual(set(fields), {"amount", "description"})
        self.assertIsInstance(fields["amount"], float)
        renamed = self.http.patch("/v1/ledger/expenses/01-01-2026:1", json={"description": "Lunch"})
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.json()["description"], "Lunch")
        self.assertEqual(renamed.json()["amount"], 12.34)
        self.assertEqual(self.http.delete("/v1/ledger/expenses/01-01-2026:1").status_code, 204)
        self.assertEqual(self.http.get("/v1/ledger/expenses").json(), {"expenses": []})
        self.assertEqual(self.create().json()["id"], "01-01-2026:2")

    def test_uses_highest_numeric_counter_of_manual_documents(self):
        for counter in (1, 2, 9, 10):
            self.client.data[("expenses", f"01-01-2026:{counter}")] = {"amount": 1.0, "description": "Manual"}
        self.assertEqual(self.create().json()["id"], "01-01-2026:11")
        # A manual write after metadata exists must also be respected.
        self.client.data[("expenses", "01-01-2026:20")] = {"amount": 2.0, "description": "Manual"}
        self.assertEqual(self.create().json()["id"], "01-01-2026:21")

    def test_sorts_dates_across_years_and_counters_numerically(self):
        for identifier in ("01-01-2026:10", "12-31-2025:1", "01-01-2026:2"):
            self.client.data[("expenses", identifier)] = {"amount": 1.0, "description": "Test"}
        response = self.http.get("/v1/ledger/expenses")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r["id"] for r in response.json()["expenses"]], ["12-31-2025:1", "01-01-2026:2", "01-01-2026:10"])

    def test_resets_counter_on_new_day(self):
        self.assertEqual(self.create().json()["id"], "01-01-2026:1")
        self.mock_clock.now.return_value = datetime(2026, 1, 2)
        self.assertEqual(self.create().json()["id"], "01-02-2026:1")
        self.mock_clock.now.assert_called_with(self.repository.timezone)

    def test_rejects_invalid_amounts_descriptions_and_ids(self):
        for amount in (0, -1, 1.234, "NaN", "Infinity", 1000000000):
            self.assertEqual(self.create(amount=amount).status_code, 422)
        self.assertEqual(self.create(description="   ").status_code, 422)
        self.assertEqual(self.http.patch("/v1/ledger/expenses/not-an-id", json={"description": "Test"}).status_code, 422)
        self.assertEqual(self.http.delete("/v1/ledger/expenses/02-30-2026:1").status_code, 422)
        self.assertEqual(self.http.patch("/v1/ledger/expenses/01-01-2026:1", json={"description": "Test"}).status_code, 404)
        self.assertFalse(self.client.data)

    def test_firestore_failure_is_reported_as_unavailable(self):
        from google.api_core.exceptions import ServiceUnavailable
        with patch.object(self.repository, "list", side_effect=ServiceUnavailable("offline")):
            self.assertEqual(self.http.get("/v1/ledger/expenses").status_code, 503)


if __name__ == "__main__":
    unittest.main()
