# Utility APIs

A small FastAPI project containing utility APIs for URL shortening, image
responses, event leaderboards, a Gauntlet lap-time tracker,
health checks, and Temporal workflows. The order API starts a workflow with the order ID, and that workflow
persists the order to Cloud Firestore through a reusable activity. It then waits
up to one hour for a success event published to Kafka before running its
completion activity.

All endpoints run from one application and are organized with `APIRouter`.
Redis stores URL-to-code mappings so generated short URLs can be resolved.

Start with [How to run the server](docs/how_to_run_server.md) for installation
and local startup instructions.

## Documentation

- [How to run the server](docs/how_to_run_server.md) — start here
- [Redis reference](docs/depdency/redis_reference.md)
- [Temporal reference](docs/depdency/temporal_reference.md)
- [Firestore reference](docs/depdency/firestore_reference.md)
- [Kafka reference](docs/depdency/kafka_reference.md)
- [Gauntlet API](docs/apis/gauntlet.md)
- [How to call the API](docs/how_to_call_api.md)
- [Project reference](docs/project_reference.md)


## Expense Ledger API

The SwiftUI Ledger uses these endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/v1/ledger/expenses` | All records ordered by date and numeric daily counter |
| POST | `/v1/ledger/expenses` | Create with `{"amount":12.34,"description":"Coffee"}` |
| PATCH | `/v1/ledger/expenses/{id}` | Rename with `{"description":"Lunch"}` |
| DELETE | `/v1/ledger/expenses/{id}` | Idempotent delete; returns an empty 204 response |

Set `FIRESTORE_EXPENSE_COLLECTION` to override the default `expenses` collection.
Each expense document contains exactly `amount` (Firestore double, in currency
units, positive and at most two decimal places) and `description` (trimmed text).
Amounts are limited to 999,999,999.99 per record. Responses include the Firestore
document ID as `id`; no date or user fields are stored in the expense document.

The server generates IDs such as `01-01-2026:1`, `01-01-2026:2`, using
`MM-DD-YYYY:counter`. `LEDGER_TIMEZONE` defaults to `America/Los_Angeles`.
The date is a calendar day, not a precise timestamp. Daily allocation and the
expense creation run in a Firestore transaction. A separate `expenses_counters`
collection (or `<configured collection>_counters`) stores the high-water counter.
It is created automatically on the first write. Existing manually entered IDs
are respected, and deletions never reset the counter. Transaction conflicts
retry through the Firestore SDK. Do not delete the counter metadata if IDs must
never be reused.

The UI calculates totals in integer cents from the complete fetched list. There
is no pagination, offline editing, automatic request retry, or user isolation in
this personal ledger version. On an ambiguous save failure, refresh before
resubmitting; a fresh POST creates a new record. Use the existing private/local
backend deployment. Firestore credentials remain server-side, using the existing
`GOOGLE_APPLICATION_CREDENTIALS`/application-default credential configuration.

Run the Ledger tests without cloud writes:

```sh
.venv/bin/python -m unittest tests.test_ledger -v
```
