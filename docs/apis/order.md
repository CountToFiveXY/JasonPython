# Order API

`POST /v1/order` starts a Temporal `OrderWorkflow`. The workflow writes the
order to Cloud Firestore through a reusable activity. A user ID is required.

## Request

```bash
curl -X POST http://127.0.0.1:8000/v1/order \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"user-123"}'
```

## Response

The endpoint responds with HTTP `201 Created`:

```json
{
  "id": "12345678-1234-1234-1234-123456789abc",
  "user_id": "user-123",
  "created": "2026-09-07T18:30:00Z",
  "expires_at": "2026-09-08T18:30:00Z",
  "status": "STARTED",
  "workflow_id": "12345678-1234-1234-1234-123456789abc"
}
```

The endpoint constructs the persistent `Order` model defined in
`src/entity/order.py`. Its HTTP `OrderRequest` and `OrderResponse` contracts are
defined separately in `src/schemas/order.py`. The router delegates creation to
`OrderService` in `src/services/order.py`, which constructs the entity and passes
its serialized fields to Temporal. The workflow
calls `write_firestore_document` to write the `orders/{id}` document with `id`,
`user_id`, `created`, `expires_at`, and `status` set to `STARTED`. The generic activity
uses an idempotent write so Temporal retries are safe and other workflows can
reuse it. The expiration timestamp is exactly 24 hours after creation, and an
enabled Firestore TTL policy on `orders.expires_at` deletes expired documents.
Deletion scheduling is managed entirely by Firestore; no Temporal cleanup
workflow is started.
The UUID is used as both the Firestore document ID and Temporal workflow ID.
The API starts the workflow but does not wait for it to finish. The workflow
waits for up to one hour for a `SUCCESS` signal. A matching Kafka message causes
the workflow to run its completion activity, update the persisted status to
`COMPLETED`, and finish:

```bash
curl -X POST http://127.0.0.1:8000/v1/messages \
  -H 'Content-Type: application/json' \
  -d '{"id":"ORDER_ID_FROM_RESPONSE","status":"SUCCESS"}'
```

See the [Firestore reference](../depdency/firestore_reference.md) for local
authentication and configuration.
