# Order API

`POST /v1/order` creates an order in Cloud Firestore and starts a Temporal
`OrderWorkflow`. A user ID is required.

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
  "workflow_id": "12345678-1234-1234-1234-123456789abc"
}
```

The `orders/{id}` Firestore document contains `id`, `user_id`, `created`, and
`expires_at`. The expiration timestamp is exactly 24 hours after creation, and
an `OrderCleanupWorkflow` waits until that age and deletes the document. A
native Firestore TTL policy on `orders.expires_at` can also be enabled as a
second cleanup mechanism.
The UUID is used as both the Firestore document ID and Temporal workflow ID.
The API starts the workflow but does not wait for it to finish. The workflow
waits for up to one hour for a `SUCCESS` signal. A matching Kafka message causes
the workflow to run its completion activity and finish:

```bash
curl -X POST http://127.0.0.1:8000/v1/messages \
  -H 'Content-Type: application/json' \
  -d '{"id":"ORDER_ID_FROM_RESPONSE","status":"SUCCESS"}'
```

See the [Firestore reference](../depdency/firestore_reference.md) for local
authentication and configuration.
